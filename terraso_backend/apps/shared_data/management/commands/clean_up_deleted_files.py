# Copyright © 2021-2023 Technology Matters
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

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.shared_data.models import DataEntry


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)

    def handle(self, *args, **kwargs):
        past_days = kwargs.get("days")

        total_files_removed = 0
        older_than_date = timezone.now() - timezone.timedelta(days=past_days)
        data_entries = (
            DataEntry.objects.deleted_only()
            .filter(
                deleted_at__date__lt=older_than_date,
                file_removed_at__isnull=True,
            )
            .iterator()
        )

        for data_entry in data_entries:
            try:
                data_entry.delete_file_on_storage()
                total_files_removed += 1
            except RuntimeError as exc:
                self.stdout.write(self.style.WARNING(f"Couldn't delete file: {exc}"))

        self.stdout.write(
            self.style.SUCCESS(f"Removed {total_files_removed} successfully"),
        )
