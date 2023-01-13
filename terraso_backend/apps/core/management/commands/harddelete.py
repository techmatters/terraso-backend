from datetime import datetime, timedelta, timezone

import structlog
from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import models
from safedelete.models import HARD_DELETE

logger = structlog.get_logger(__name__)


class Command(BaseCommand):

    DEFAULT_DELETION_GAP = timedelta(days=settings.HARDDELETE_DELETION_GAP)

    help = "Hard delete rows in database that were soft-deleted before a specified time"

    def add_arguments(self, parser):
        parser.add_argument(
            "--exec_time",
            type=datetime.fromisoformat,
            default=datetime.now(timezone.utc),
            help="Manually set the execution time. Default is to use the current time.",
        )
        parser.add_argument(
            "--deletion_gap",
            type=lambda x: timedelta(days=int(x)),
            default=self.DEFAULT_DELETION_GAP,
            help="Set the deletion gap. Any row soft-deleted more than deletion_gap days "
            "ago will be hard deleted / removed from the database.",
        )

    @staticmethod
    def all_objects(cutoff_date):
        app_models = apps.get_models()
        objects = []
        for model in app_models:
            for field in model._meta.fields:
                if field.name == "deleted_at" and isinstance(field, models.fields.DateTimeField):
                    objects.extend(
                        model.objects.all(force_visibility=True)
                        .filter(deleted_at__lte=cutoff_date)
                        .all()
                    )
                    continue
        return objects

    def handle(self, *args, **options):
        exec_time = options["exec_time"]
        deletion_gap = options["deletion_gap"]
        cutoff_date = exec_time - deletion_gap
        to_delete = self.all_objects(cutoff_date)
        for obj in to_delete:
            obj.delete(force_policy=HARD_DELETE)
