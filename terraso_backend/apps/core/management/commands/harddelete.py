# Copyright © 2023 Technology Matters
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
from datetime import datetime, timedelta, timezone

import structlog
from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import models, transaction
from safedelete.models import HARD_DELETE

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    DEFAULT_DELETION_GAP = timedelta(days=settings.HARD_DELETE_DELETION_GAP)

    help = "Hard delete rows in database that were soft-deleted before a specified time"

    def add_arguments(self, parser):
        parser.add_argument(
            "--deletion_gap",
            type=lambda x: timedelta(days=int(x)),
            default=self.DEFAULT_DELETION_GAP,
            help="Set the deletion gap. Any row soft-deleted more than deletion_gap days "
            "ago will be hard deleted / removed from the database.",
        )

    @staticmethod
    def all_objects(cutoff_date):
        """All soft-deleted rows past the date cutoff, in order of soft-deletion. The sort is for safety in dependency ordering: dependents
        purged before their dependencies to avoid dangling reference errors.

        Skips proxy models — they share the underlying table with their
        concrete parent, so without this guard the same row would be
        queued twice (once as the parent, once as the proxy)."""
        app_models = apps.get_models()
        objects = []
        for model in app_models:
            if model._meta.proxy:
                continue
            for field in model._meta.fields:
                if field.name == "deleted_at" and isinstance(field, models.fields.DateTimeField):
                    objects.extend(
                        model.objects.all(force_visibility=True)
                        .filter(deleted_at__lte=cutoff_date)
                        .all()
                    )
                    continue
        objects.sort(key=lambda o: o.deleted_at)
        return objects

    def handle(self, *args, **options):
        exec_time = datetime.now(timezone.utc)
        deletion_gap = options["deletion_gap"]
        cutoff_date = exec_time - deletion_gap
        to_delete = self.all_objects(cutoff_date)
        succeeded = 0
        failed = 0
        for obj in to_delete:
            # Per-row try/except + atomic isolates each delete: one row's
            # IntegrityError (e.g. an FK pointing at a not-yet-purged row,
            # or an admin-undeleted referencer to a soft-deleted target)
            # logs to Sentry but doesn't abort the batch. The next cron
            # run picks the row up again and retries.
            model_label = type(obj)._meta.label
            pk = str(obj.pk)
            try:
                with transaction.atomic():
                    obj.delete(force_policy=HARD_DELETE)
                succeeded += 1
                logger.info("harddelete.row_succeeded", model=model_label, pk=pk)
            except Exception as err:
                failed += 1
                logger.error(
                    "harddelete.row_failed",
                    model=model_label,
                    pk=pk,
                    error=str(err),
                    error_type=type(err).__name__,
                )
        logger.info("harddelete.run_complete", succeeded=succeeded, failed=failed)
