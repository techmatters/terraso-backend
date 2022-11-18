import json
import os
import re
from configparser import ConfigParser
from pathlib import Path
from tempfile import mkstemp
from urllib.parse import urlsplit, urlunsplit

import structlog
from django.apps import apps
from django.conf import settings
from django.contrib.sessions.models import Session
from django.core import management
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.models.fields import URLField
from django.db.models.fields.related import ForeignKey
from psycopg2 import sql

from apps.core.models import User

from ._backup_storage import S3BackupStorage

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    """Load data from a backup into the database"""

    help = "Load backup JSON files."

    # This is for core migrations that should be skipped. Could be for several reasons:
    # - The table is needed throughtout the migration so it is not dropped.
    # - The migration is a data migration, so it introduces data that will already be in the backup
    CORE_MIGRATIONS_TO_SKIP = [15]

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
        parser.add_argument(
            "--save-user",
            help="ID of a user who should be inserted into the new database."
            " Any active sessions will be saved as well.",
        )
        parser.add_argument(
            "--save-session", help="Primary key of session data that should be saved."
        )

    @staticmethod
    def _convert_url(url, patterns):
        url_parts = urlsplit(url)
        matches = [new_url for new_url, pattern in patterns if pattern.match(url_parts.hostname)]
        if not matches:
            return
        new_hostname, *_ = matches
        # deal with case schema in hostname
        if (split_again := urlsplit(new_hostname)).scheme:
            new_hostname = split_again.hostname
        scheme, _, path, query, fragment = url_parts
        return urlunsplit((scheme, new_hostname, path, query, fragment))

    @staticmethod
    def _load_url_rewrites(path):
        config = ConfigParser()
        config.read(path)
        patterns = []
        sections = set(config.sections())
        sections.remove("service")
        for key in sections:
            block = config[key]
            source_url = re.compile(block["source_bucket_url"])
            target_url = block["target_bucket_url"]
            patterns.append((target_url, source_url))
        return patterns

    @classmethod
    def _rewrite_urls(cls, patterns):
        models = apps.get_models()
        for model in models:
            url_fields = [
                field for field in model._meta.get_fields() if isinstance(field, URLField)
            ]
            if not url_fields:
                continue
            objects = model.objects.all().only(*[field.name for field in url_fields])
            for obj in objects:
                for field in url_fields:
                    url = getattr(obj, field.name)
                    if not url:
                        continue
                    if new_url := cls._convert_url(url, patterns):
                        setattr(obj, field.name, new_url)
                if not obj.clean():
                    obj.save()

    @staticmethod
    def _reset_user_id(old_user_id, new_user_id):
        """Change links from new user id to old user id. This is so the logged in user will
        stay logged in."""
        models = apps.get_models()
        for model in models:
            foreign_keys = []
            for field in model._meta.get_fields():
                if isinstance(field, ForeignKey) and field.related_model == User:
                    foreign_keys.append(field)
            if not foreign_keys:
                continue
            old = {field.name: str(old_user_id) for field in foreign_keys}
            new = {field.name: str(new_user_id) for field in foreign_keys}
            model.objects.filter(**new).update(**old)

    @staticmethod
    def _find_latest_backup_dir(directory):
        """Find the latest backup in a directory.

        Backups are named according to the date they are created.
        """
        files = sorted([f for f in directory.glob("backup*") if f.is_file()])
        if len(files) < 2:
            raise RuntimeError(f"Couldn't find any backup files in {directory}")
        # default is to sort ascending, so latest files at end
        data_file, migrations_file = files[-2:]
        return data_file, migrations_file

    @staticmethod
    def _copy_s3_file(storage, path, suffix):
        """Copies the S3 file to a temporary file on local filesystem."""
        _, tmp_file_path = mkstemp(suffix=suffix)
        bucket_name = storage.bucket.name
        with open(tmp_file_path, "wb") as temp_file:
            storage.bucket.meta.client.download_fileobj(bucket_name, path, temp_file)
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
            if user_id := options.get("save_user"):
                user = User.objects.get(id=user_id)
            else:
                user = None
            pass
            if session_pk := options.get("save_session"):
                session = Session.objects.get(session_key=session_pk)
            else:
                session = None

        except Exception:
            msg = "Error accessing user and session"
            logger.exception(msg)
            raise CommandError(msg)

        try:
            if options["s3"]:
                data, migrations_file = self._find_last_backup_s3()
            else:
                data, migrations_file = self._find_latest_backup_dir(options["directory"])
            with open(migrations_file, "rb") as fp:
                migrations = json.load(fp)
        except Exception:
            msg = "Failure loading backup files"
            logger.exception(msg)
            raise CommandError(msg)

        def cleanup():
            if options["s3"]:
                for path in data, migrations_file:
                    os.unlink(path)

        with connection.cursor() as cursor:
            try:
                # background task progress is saved in a DB table
                # need to make sure this table is not deleted. otherwise things will break
                cursor.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
                    "AND tablename NOT IN ('core_backgroundtask', 'django_session');"
                )
                tables_to_drop = cursor.fetchall()
                if session_pk:
                    cursor.execute(
                        "DELETE FROM django_session WHERE session_key != %s", (str(session_pk),)
                    )
                else:
                    cursor.execute("DELETE FROM django_session")
                for (table,) in tables_to_drop:
                    cursor.execute(
                        sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(sql.Identifier(table))
                    )
            except Exception:
                msg = "Command failed resetting database"
                logger.exception(msg)
                connection.rollback()
                cleanup()
                raise CommandError(msg)

            connection.commit()

        try:
            for app_label, version in migrations.items():
                if app_label == "core":
                    # need to skip the migration that creates the background tasks
                    for version in self.CORE_MIGRATIONS_TO_SKIP:
                        management.call_command(
                            "migrate", "core", "{0:0>4}".format(version - 1), verbosity=0
                        )
                        management.call_command(
                            "migrate", "core", "{0:0>4}".format(version), fake=True, verbosity=0
                        )
                    management.call_command("migrate", "core", verbosity=0)
                kwargs = {}
                if app_label == "sessions":
                    kwargs["fake_initial"] = True
                management.call_command("migrate", app_label, verbosity=0, **kwargs)

            management.call_command(
                "loaddata",
                str(data.resolve()) if isinstance(data, Path) else data,
                exclude=[
                    "core.BackgroundTask",
                    "contenttypes.contenttype",
                    "auth.Permission",
                    "sessions.Session",
                    "admin.LogEntry",
                ],
            )

            if user:
                try:
                    # here we want to ensure that the currently logged in user (i.e. the user
                    # triggering the reset) retains the same user ID in the restored database.
                    # This is to make sure the login status remains valid
                    new_user = User.objects.get(email=user.email)
                    # provide a fake "email" not in the database
                    user.email = str(user.id)
                    user.save()
                    self._reset_user_id(new_user.id, user.id)
                    # copy fields from new user to old
                    for field in User._meta.fields:
                        if field.name in ("id", "password", "is_staff"):
                            continue
                        setattr(user, field.name, getattr(new_user, field.name))
                    new_user.delete()
                    user.save()

                except User.DoesNotExist:
                    user.save()

            if session:
                session.save()

            cleanup()

            config = Path(settings.DB_RESTORE_CONFIG_FILE)
            if not config.is_file() :
                raise CommandError(
                    f"Path supplied for URL rewrites is not a file: {str(config)}. "
                    "URL rewrites not applied."
                )
            if not os.access(config, os.R_OK) :
                raise CommandError(
                    f"Cannot read config file: {str(config)}. "
                    "URL rewrites not applied."
                )

            patterns = self._load_url_rewrites(config)
            self._rewrite_urls(patterns)

        except Exception:
            msg = "Exception triggered in restore"
            logger.exception(msg)
            raise CommandError(msg)
