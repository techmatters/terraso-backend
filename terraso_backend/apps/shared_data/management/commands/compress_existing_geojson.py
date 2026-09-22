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

from botocore.exceptions import ClientError
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from apps.shared_data.models import VisualizationConfig
from apps.shared_data.services import GEOJSON_CONTENT_TYPE, geojson_upload_service


class Command(BaseCommand):
    """Compress existing generated layer GeoJSON objects in S3 in place.

    Compression is encoded as per-object HTTP metadata (Content-Encoding:
    gzip), not as a key rename or a DB flag: browsers and mapbox-gl
    transparently decompress, keys stay identical, persisted references
    (VisualizationConfig.geojson_s3_key, story-map configuration JSON,
    presigned URLs) remain valid, and plain and gzipped objects can coexist
    while the backfill is in progress.

    Idempotency: an object whose Content-Encoding is already gzip is skipped on
    the head_object alone.

    Scope of enumeration: keys come from VisualizationConfig.geojson_s3_key, so
    objects orphaned by a deleted row are not reachable by this command.
    """

    help = (
        "gzip-compresses existing generated layer GeoJSON objects (geojson/...) in "
        "S3 in place, setting Content-Encoding: gzip and Cache-Control without "
        "renaming keys"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing anything",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        stats = {
            "scanned": 0,
            "compressed": 0,
            "would_compress": 0,
            "already": 0,
            "missing": 0,
            "invalid": 0,
            "failed": 0,
            "bytes_before": 0,
            "bytes_after": 0,
        }

        for key in self._visualization_config_keys():
            stats["scanned"] += 1
            self._process_key(stats, key, dry_run)

        self._print_summary(stats, dry_run)

    def _visualization_config_keys(self):
        """Yield generated layer GeoJSON object keys from the DB."""
        queryset = VisualizationConfig.objects.filter(geojson_s3_key__isnull=False).exclude(
            geojson_s3_key=""
        )
        for config in queryset.only("id", "geojson_s3_key").iterator():
            yield config.geojson_s3_key

    def _process_key(self, stats, key, dry_run):
        storage = geojson_upload_service.storage
        client = storage.bucket.meta.client
        try:
            head = client.head_object(Bucket=storage.bucket_name, Key=key)
        except ClientError as error:
            if self._is_missing(error):
                stats["missing"] += 1
                self.stdout.write(f"SKIP {key}: object missing from S3")
            else:
                stats["failed"] += 1
                self.stdout.write(self.style.ERROR(f"ERROR {key}: {error}"))
            return
        except Exception as error:
            stats["failed"] += 1
            self.stdout.write(self.style.ERROR(f"ERROR {key}: {error}"))
            return

        if head.get("ContentEncoding") == "gzip":
            stats["already"] += 1
            return

        try:
            plaintext = storage.open(key, "rb").read()
            json.loads(plaintext)  # raises for anything that is not JSON
        except Exception:
            stats["invalid"] += 1
            self.stdout.write(self.style.WARNING(f"SKIP {key}: stored bytes are not valid JSON"))
            return

        stats["bytes_before"] += head["ContentLength"]

        if dry_run:
            # Preview through the storage's own compressor so the reported size
            # is exactly what a real run would write (deterministic: level 6,
            # mtime=0).
            compressed = storage._gzip_content(ContentFile(plaintext)).read()
            stats["would_compress"] += 1
            stats["bytes_after"] += len(compressed)
            self.stdout.write(
                f"WOULD COMPRESS {key}: {head['ContentLength']} -> {len(compressed)} bytes"
            )
            return

        try:
            # Hand the plaintext to overwrite(): the storage compresses exactly
            # once and tags it with the same metadata as the write path
            # (_get_write_parameters is the single source of truth).
            storage.overwrite(key, ContentFile(plaintext))

            # Verify what actually landed.
            stored = storage.open(key, "rb").read()
            if gzip.decompress(stored) != plaintext:
                raise ValueError("stored object does not gunzip back to the original content")
            stored_head = client.head_object(Bucket=storage.bucket_name, Key=key)
            if stored_head.get("ContentEncoding") != "gzip":
                raise ValueError("stored object is missing Content-Encoding: gzip")
            if stored_head.get("ContentType") != GEOJSON_CONTENT_TYPE:
                raise ValueError(
                    f"stored object Content-Type {stored_head.get('ContentType')!r} "
                    f"!= expected {GEOJSON_CONTENT_TYPE!r}"
                )
        except Exception as error:
            stats["failed"] += 1
            self.stdout.write(self.style.ERROR(f"ERROR {key}: {error}"))
            return

        stats["compressed"] += 1
        stats["bytes_after"] += len(stored)
        self.stdout.write(
            f"COMPRESSED {key}: {head['ContentLength']} -> {len(stored)} bytes "
            f"(content_type={stored_head['ContentType']})"
        )

    @staticmethod
    def _is_missing(error):
        return error.response.get("Error", {}).get("Code") in ("404", "NoSuchKey")

    def _print_summary(self, stats, dry_run):
        action = "Would compress" if dry_run else "Compressed"
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{action}: {stats['would_compress'] if dry_run else stats['compressed']} "
                f"| Scanned: {stats['scanned']} "
                f"| Already compressed: {stats['already']} "
                f"| Missing: {stats['missing']} "
                f"| Invalid: {stats['invalid']} "
                f"| Failed: {stats['failed']}"
            )
        )
        before = stats["bytes_before"]
        after = stats["bytes_after"]
        if before:
            reduction = (1 - after / before) * 100
            self.stdout.write(
                self.style.SUCCESS(
                    f"Storage bytes: {before} -> {after} "
                    f"({before - after} saved, {reduction:.1f}% reduction)"
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("Storage bytes: 0 -> 0 (nothing to rewrite)"))
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: no objects were written"))
