# Copyright © 2026 Technology Matters
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see https://www.gnu.org/licenses/.

import gzip
import json

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.shared_data.geojson_upload import get_geojson_from_data_entry
from apps.shared_data.models import VisualizationConfig
from apps.shared_data.services import geojson_upload_service

# Scope: the CSV/dataset pipeline (.csv/.xls/.xlsx) and the KML pipeline
# (.kml/.kmz). Adjust here if other types should be covered later.
DATASET_EXTENSIONS = tuple(settings.DATA_ENTRY_SPREADSHEET_TYPES.keys())
KML_EXTENSIONS = (".kml", ".kmz")
RESOURCE_TYPES = [ext.lstrip(".") for ext in DATASET_EXTENSIONS + KML_EXTENSIONS]

STATUSES = (
    "MATCH",
    "DIFF",
    "STALE",
    "UNREADABLE",
    "GENERATES",
    "NO_GEOJSON",
    "GENERATION_ERROR",
)

# Objects written through GzipStorageMixin are stored gzip-compressed (with
# Content-Encoding: gzip so browsers transparently decompress); legacy plain
# objects can coexist with them. The gzip magic number cannot start valid
# JSON, so sniffing it is unambiguous.
GZIP_MAGIC = b"\x1f\x8b"


def _first_feature_diff(stored, generated):
    """Short human-readable description of the first stored/generated diff."""
    stored_features = stored.get("features") or []
    generated_features = generated.get("features") or []
    for index, (stored_f, generated_f) in enumerate(zip(stored_features, generated_features)):
        if stored_f != generated_f:
            kind = (
                "geometry"
                if stored_f.get("geometry") != generated_f.get("geometry")
                else "properties"
            )
            return f"first differing feature {index}: {kind}"
    return (
        f"feature counts differ (stored {len(stored_features)}, "
        f"generated {len(generated_features)})"
    )


class Command(BaseCommand):
    help = (
        "Re-runs the GeoJSON generation pipeline for every CSV/dataset and KML "
        "visualization config and compares the result with the object on S3, "
        "flagging any diffs. Read-only: never writes to S3 or the database."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Check at most N visualization configs (for smoke runs).",
        )

    def handle(self, *args, **options):
        vcs = (
            VisualizationConfig.objects.filter(
                data_entry__isnull=False,
                data_entry__deleted_at__isnull=True,
                data_entry__resource_type__in=RESOURCE_TYPES,
            )
            .select_related("data_entry")
            .order_by("created_at")
        )
        if options["limit"]:
            vcs = vcs[: options["limit"]]

        counts = dict.fromkeys(STATUSES, 0)
        for vc in vcs:
            status, detail = self._check_vc(vc)
            counts[status] += 1
            self.stdout.write(
                f"{status:<16} vc={vc.id} ({vc.title}) de={vc.data_entry.resource_type} — {detail}"
            )

        self.stdout.write(self.style.SUCCESS("\nSummary"))
        for status in STATUSES:
            if counts[status]:
                self.stdout.write(f"  {status:<16} {counts[status]}")

    def _check_vc(self, vc):
        """Re-run generation for one VC and compare with its S3 object."""
        try:
            generated = get_geojson_from_data_entry(vc.data_entry, vc)
        except Exception as e:  # noqa: BLE001 - the command must survive any failure
            return "GENERATION_ERROR", f"{type(e).__name__}: {e}"

        if generated is None:
            if vc.geojson_s3_key:
                return "STALE", f"S3 key {vc.geojson_s3_key} is set but generation yields nothing"
            return "NO_GEOJSON", "generation returned no features"

        if not vc.geojson_s3_key:
            return "GENERATES", (
                f"generation succeeds ({len(generated['features'])} features); nothing on S3 yet"
            )

        try:
            raw = geojson_upload_service.get_file(vc.geojson_s3_key, "rb").read()
            if raw[:2] == GZIP_MAGIC:
                raw = gzip.decompress(raw)
            stored = json.loads(raw)
        except Exception as e:  # noqa: BLE001 - missing object, S3 errors, bad JSON...
            return "UNREADABLE", f"S3 key {vc.geojson_s3_key}: {type(e).__name__}: {e}"

        if stored == generated:
            return "MATCH", f"{len(generated['features'])} features, identical to S3"

        counts = (
            f"stored {len(stored.get('features') or [])} vs generated "
            f"{len(generated.get('features') or [])} features"
        )
        return "DIFF", f"{counts}; {_first_feature_diff(stored, generated)}"
