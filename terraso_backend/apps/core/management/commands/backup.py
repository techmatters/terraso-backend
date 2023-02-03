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

import json
import os
import traceback
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core import management
from django.core.management.base import BaseCommand
from django.db import connection

from ._backup_storage import S3BackupStorage


class Command(BaseCommand):
    """Backs up the application database to JSON files."""

    help = "Back up database to JSON files"

    def add_arguments(self, parser):
        parser.add_argument("--s3", action="store_true", help="Store backup in S3 bucket")

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
        if options["s3"]:
            # don't need to keep local copy if uploaded to bucket
            tempdir = TemporaryDirectory()
            tempdir_path = Path(tempdir.name)
            data_file_name = data_file
            migration_file_name = migration_file
            data_file = str(tempdir_path / data_file)
            migration_file = str(tempdir_path / migration_file)

        def cleanup():
            for filepath in data_file, migration_file:
                if os.path.exists(filepath):
                    os.unlink(filepath)

        try:
            management.call_command(
                "dumpdata",
                output=data_file,
                verbosity=0,
                exclude=[
                    "core.BackgroundTask",
                    "contenttypes.contenttype",
                    "auth.Permission",
                    "sessions.Session",
                ],
                natural_foreign=True,
                natural_primary=True,
            )

            migrations = self._query_migration_versions()
            self._save_migration_versions(migration_file, migrations)

            if options["s3"]:
                storage = S3BackupStorage()
                with open(data_file, "rb") as data_fp, open(migration_file, "rb") as migration_fp:
                    storage.save(data_file_name, data_fp)
                    storage.save(migration_file_name, migration_fp)

        except Exception:
            traceback.print_exc()
            return 1
        else:
            return 0
        finally:
            if tempdir:
                tempdir.cleanup()
