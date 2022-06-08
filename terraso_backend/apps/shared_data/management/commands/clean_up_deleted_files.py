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
            DataEntry.objects.deleted_only().filter(deleted_at__date__lt=older_than_date).iterator()
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
