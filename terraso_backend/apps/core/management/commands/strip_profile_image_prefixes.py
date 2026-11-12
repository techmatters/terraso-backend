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
"""Strip host/bucket prefixes from stored profile_image values.

One-off data migration for the switch from storing a full URL in
User/Landscape.profile_image to storing just the S3 object key. For each row it
rewrites e.g.

    https://images.terraso.org/<id>/profile-image_2          (CDN / virtual style)
    http://host:9000/<bucket>/<id>/profile-image_2           (local silo path style)

down to the bare key `<id>/profile-image_2`. The servable URL is then rebuilt on
read from PROFILE_IMAGES_BASE_URL (apps.storage.services.build_profile_image_url).

Safe to run repeatedly: rows already in key form are left untouched. Use
--dry-run first to see counts without writing. Rows whose value doesn't match
the expected `<id>/profile-image...` shape are reported and skipped, never
rewritten blindly.

Only active (non-soft-deleted) rows are processed.
"""

from urllib.parse import urlparse

from django.core.management.base import BaseCommand

from apps.core.models import User
from apps.core.models.landscapes import Landscape


def key_from_value(obj_id, value):
    """Return the bare S3 key for a stored profile_image value.

    - Empty or already-a-key (no http scheme) -> returned unchanged (idempotent).
    - A full URL -> the path from `<id>/` onward, dropping scheme/host and any
      leading bucket segment (anchored on the row's own id, so it works for both
      virtual-hosted CDN URLs and path-style silo URLs).
    - Unexpected shape (no `<id>/` found) -> None, so the caller can skip it.
    """
    if not value or not value.startswith(("http://", "https://")):
        return value
    path = urlparse(value).path.lstrip("/")
    anchor = f"{obj_id}/"
    idx = path.find(anchor)
    if idx == -1:
        return None
    return path[idx:]


class Command(BaseCommand):
    help = "Rewrite User/Landscape profile_image from a full URL to the bare S3 key."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        grand_updated = grand_skipped = grand_unmatched = 0

        for model, label in ((User, "User"), (Landscape, "Landscape")):
            updated = skipped = unmatched = 0
            for obj in model.objects.exclude(profile_image="").iterator():
                value = obj.profile_image
                key = key_from_value(obj.id, value)
                if key is None:
                    unmatched += 1
                    self.stderr.write(f"  [skip] {label} {obj.id}: can't derive key from {value!r}")
                    continue
                if key == value:
                    skipped += 1
                    continue
                if not dry_run:
                    obj.profile_image = key
                    obj.save(update_fields=["profile_image"])
                updated += 1

            self.stdout.write(
                f"{label}: {updated} to rewrite, {skipped} already keys, {unmatched} unmatched"
            )
            grand_updated += updated
            grand_skipped += skipped
            grand_unmatched += unmatched

        verb = "Would rewrite" if dry_run else "Rewrote"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {grand_updated} row(s); {grand_skipped} already keys; "
                f"{grand_unmatched} unmatched."
            )
        )
