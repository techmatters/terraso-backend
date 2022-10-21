import json
from pathlib import Path

import structlog
from django.core import management
from django.core.management.base import BaseCommand
from django.db import connection

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    """Load data from a backup into the database"""

    help = "Load backup JSON files."

    def add_arguments(self, parser):
        parser.add_argument(
            "-d",
            "--directory",
            type=Path,
            default=Path("."),
            help="Directory where backups can be found",
        )

    @staticmethod
    def _find_latest_backup(directory):
        """Find the latest backup in a directory.

        Backups are named according to the date they are created.
        """
        files = sorted([f for f in directory.glob("backup*") if f.is_file()])
        if len(files) < 2:
            raise RuntimeError(f"Couldn't find any backup files in {directory}")
        # default is to sort ascending, so latest files at end
        data, migrations_file = files[-2:]
        with migrations_file.open() as fp:
            migration_versions = json.load(fp)
        return migration_versions, data

    def handle(self, *args, **options):
        try:
            migrations, data = self._find_latest_backup(options["directory"])
        except Exception:
            logger.exception("Failure loading backup files")
            exit(1)

        with connection.cursor() as cursor:
            try:
                cursor.execute("DROP SCHEMA IF EXISTS public CASCADE")
                cursor.execute("CREATE SCHEMA public")
            except Exception:
                logger.exception("Failed to reset schema")
                connection.rollback()
                exit(1)

            connection.commit()

            for app_label, version in migrations.items():
                management.call_command("migrate", app_label, version, verbosity=0)

            management.call_command("loaddata", str(data.resolve()))

            # migrate to latest version, if there is a difference
            management.call_command("migrate", verbosity=0)
