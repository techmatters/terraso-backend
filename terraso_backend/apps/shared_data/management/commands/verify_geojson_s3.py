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
import uuid

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.shared_data.geojson_upload import (
    get_geojson_from_data_entry,
    upload_geojson_to_s3,
)
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

# Statuses that regeneration can fix: generation succeeded but the stored
# object is missing (GENERATES), unreadable (UNREADABLE) or outdated (DIFF).
# MATCH needs no repair; STALE/NO_GEOJSON/GENERATION_ERROR mean generation
# yields nothing or fails, so re-running it cannot help.
REPAIRABLE_STATUSES = ("DIFF", "UNREADABLE", "GENERATES")

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
        "flagging any diffs. Pass VC ids to check only those configs. With "
        "--repair, regenerate the S3 object for statuses where regeneration "
        "can fix the mismatch (DIFF, UNREADABLE, GENERATES by default; "
        "--repair=STATUS[,STATUS...] restricts the set)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--repair",
            nargs="?",
            const="",
            default=None,
            metavar="STATUS[,STATUS...]",
            help=(
                "Regenerate the S3 geojson for VCs whose status is in the "
                "repair set. Bare --repair repairs DIFF, UNREADABLE and "
                "GENERATES; --repair=DIFF,GENERATES restricts the set "
                "(names must be valid statuses)."
            ),
        )
        parser.add_argument(
            "vc_ids",
            nargs="*",
            metavar="VC_ID",
            help="Optional visualization config UUIDs: check (and repair) only these.",
        )

    def handle(self, *args, **options):
        repair_statuses = self._resolve_repair_statuses(options["repair"])

        if options["vc_ids"]:
            vcs, missing = self._resolve_named_vcs(options["vc_ids"])
            for missing_id in missing:
                self.stdout.write(f"WARNING  vc={missing_id} not found")
        else:
            vcs = (
                VisualizationConfig.objects.filter(
                    data_entry__isnull=False,
                    data_entry__deleted_at__isnull=True,
                    data_entry__resource_type__in=RESOURCE_TYPES,
                )
                .select_related("data_entry")
                .order_by("created_at")
            )

        counts = dict.fromkeys(STATUSES, 0)
        repaired = 0
        repair_failed = 0
        for vc in vcs:
            if vc.data_entry_id is None:
                self.stdout.write(f"SKIPPED  vc={vc.id} ({vc.title}) — no data entry")
                continue
            status, detail = self._check_vc(vc)
            counts[status] += 1
            suffix = ""
            if repair_statuses and status in repair_statuses:
                ok, outcome = self._repair_vc(vc)
                suffix = f" (REPAIRED -> {outcome})" if ok else f" (REPAIR_FAILED: {outcome})"
                if ok:
                    repaired += 1
                else:
                    repair_failed += 1
            self.stdout.write(
                f"{status:<16} vc={vc.id} ({vc.title}) "
                f"de={vc.data_entry.resource_type} — {detail}{suffix}"
            )

        self.stdout.write(self.style.SUCCESS("\nSummary"))
        for status in STATUSES:
            if counts[status]:
                self.stdout.write(f"  {status:<16} {counts[status]}")
        if repaired:
            self.stdout.write(f"  {'REPAIRED':<16} {repaired}")
        if repair_failed:
            self.stdout.write(f"  {'REPAIR_FAILED':<16} {repair_failed}")

    def _resolve_repair_statuses(self, repair_arg):
        """Turn the --repair argument into the set of statuses to repair.

        Bare --repair (empty string) means the default repairable set;
        --repair=DIFF,GENERATES restricts it. Names are validated against
        STATUSES to catch typos; valid but non-repairable names are accepted
        yet never trigger a repair.
        """
        if repair_arg is None:
            return set()
        tokens = [token.strip().upper() for token in repair_arg.split(",") if token.strip()]
        invalid = [token for token in tokens if token not in STATUSES]
        if invalid:
            raise CommandError(
                f"Unknown status for --repair: {', '.join(invalid)}. "
                f"Valid statuses: {', '.join(STATUSES)}."
            )
        for token in tokens:
            if token not in REPAIRABLE_STATUSES:
                self.stdout.write(f"WARNING  status {token} is not repairable; it will be skipped")
        if not tokens:
            return set(REPAIRABLE_STATUSES)
        return set(tokens) & set(REPAIRABLE_STATUSES)

    def _resolve_named_vcs(self, vc_ids):
        """Resolve explicit VC ids (in order), reporting unresolvable ones."""
        vcs = []
        missing = []
        for token in vc_ids:
            try:
                vc_uuid = uuid.UUID(token)
            except ValueError:
                missing.append(token)
                continue
            vc = VisualizationConfig.objects.filter(pk=vc_uuid).first()
            if vc is None:
                missing.append(token)
                continue
            vcs.append(vc)
        return vcs, missing

    def _repair_vc(self, vc):
        """Regenerate the S3 object for one VC. Returns (ok, key or error)."""
        try:
            new_key = upload_geojson_to_s3(vc.id)
        except Exception as e:  # noqa: BLE001 - a repair must never abort the run
            return False, f"{type(e).__name__}: {e}"
        if not new_key:
            return False, "generation returned no data"
        return True, new_key

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

        # Normalize to the JSON round-trip form the uploader serializes:
        # shapely mapping() yields coordinate tuples, while the stored object
        # (JSON through S3) has lists — compare apples to apples.
        generated = json.loads(json.dumps(generated))

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
