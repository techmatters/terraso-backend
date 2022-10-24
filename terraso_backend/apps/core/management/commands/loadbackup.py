import json
import os
from pathlib import Path
from tempfile import mkstemp

import structlog
from django.core import management
from django.core.management.base import BaseCommand
from django.db import connection

from ._backup_storage import S3BackupStorage

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    """Load data from a backup into the database"""

    help = "Load backup JSON files."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "-d",
            "--directory",
            type=Path,
            default=Path("."),
            help="Directory where backups can be found",
        )
        group.add_argument("--s3", action="store_true", help="Retrieve backups from S3 bucket.")

    @staticmethod
    def _find_latest_backup_dir(directory):
        """Find the latest backup in a directory.

        Backups are named according to the date they are created.
        """
        files = sorted([f for f in directory.glob("backup*") if f.is_file()])
        if len(files) < 2:
            raise RuntimeError(f"Couldn't find any backup files in {directory}")
        # default is to sort ascending, so latest files at end
        return files[-2:]

    @staticmethod
    def _copy_s3_file(storage, path, suffix):
        """Copies the S3 file to a temporary file on local filesystem."""
        _, tmp_file_path = mkstemp(suffix=suffix)
        with storage.open(path, "rb") as fp, open(tmp_file_path, "wb") as temp_file:
            for chunk in fp.chunks():
                temp_file.write(chunk)
        return tmp_file_path

    @classmethod
    def _find_last_backup_s3(cls):
        storage = S3BackupStorage()
        _dirs, files = storage.listdir(".")
        files.sort()
        data_file, migrations_file = [
            cls._copy_s3_file(storage, path, suffix)
            for path, suffix in zip(files[-2:], (".json.gz", ".json"))
        ]
        return data_file, migrations_file

    def handle(self, *args, **options):
        try:
            if options["s3"]:
                data, migrations_file = self._find_last_backup_s3()
            else:
                data, migrations_file = self._find_latest_backup_dir(options["directory"])
            with open(migrations_file, "rb") as fp:
                migrations = json.load(fp)
        except Exception:
            logger.exception("Failure loading backup files")
            exit(1)

        def cleanup():
            if options["s3"]:
                for path in data, migrations_file:
                    os.unlink(path)

        with connection.cursor() as cursor:
            try:
                cursor.execute("DROP SCHEMA IF EXISTS public CASCADE")
                cursor.execute("CREATE SCHEMA public")
            except Exception:
                logger.exception("Failed to reset schema")
                connection.rollback()
                cleanup()
                exit(1)

            connection.commit()

        for app_label, version in migrations.items():
            management.call_command("migrate", app_label, version, verbosity=0)

        management.call_command("loaddata", str(data.resolve()) if isinstance(data, Path) else data)

        # migrate to latest version, if there is a difference
        management.call_command("migrate", verbosity=0)

        cleanup()
