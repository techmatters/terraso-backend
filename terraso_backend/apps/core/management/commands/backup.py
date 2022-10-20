import json
import os
import traceback
from datetime import datetime

from django.core import management
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    """Backs up the application database to JSON files."""

    help = "Back up database to JSON files"

    @staticmethod
    def _query_migration_versions():
        """Get the migrations applied on the current DB."""
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT DISTINCT ON (app) app, name
                   FROM django_migrations
                    ORDER BY app, name DESC"""
            )
            rows = cursor.fetchall()
        return dict(rows)

    @staticmethod
    def _save_migration_versions(filename, migration_versions):
        """Write the migration versions to a JSON file. For now."""
        with open(filename, "w") as fp:
            json.dump(migration_versions, fp)

    @staticmethod
    def _generate_filenames():
        """Generate a filename based on current date."""
        base = "backup_" + datetime.now().isoformat()
        return (base + "_data.json.gz", base + "_migrations.json")

    def handle(self, *args, **options):
        """Command "main method"."""
        data_file, migration_file = self._generate_filenames()

        try:
            management.call_command("dumpdata", output=data_file, verbosity=0)

            migrations = self._query_migration_versions()
            self._save_migration_versions(migration_file, migrations)
        except Exception:
            traceback.print_exc()
            for filepath in data_file, migration_file:
                if os.path.exists(filepath):
                    os.unlink(filepath)
