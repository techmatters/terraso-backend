from enum import Enum
from typing import Optional

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models


class Events(Enum):
    CREATE: str = "CREATE"
    READ: str = "READ"
    CHANGE: str = "CHANGE"
    DELETE: str = "DELETE"

    @classmethod
    def choices(cls):
        return [(key.value, key.name) for key in cls]


class Log(models.Model):
    """
    Log model for audits logs
    """

    timestamp = models.DateTimeField(auto_now_add=True)
    client_timestamp = models.DateTimeField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="user"
    )
    user_human_readable = models.CharField(max_length=255)
    event = models.CharField(max_length=50, choices=Events.choices(), default=Events.CREATE)

    resource_id = models.UUIDField()
    resource_content_type = models.ForeignKey(
        "contenttypes.ContentType",
        on_delete=models.CASCADE,
        verbose_name="content type",
        blank=True,
        null=True,
    )
    resource_object = GenericForeignKey("resource_content_type", "resource_id")
    resource_json_repr = models.JSONField()
    resource_human_readable = models.CharField(max_length=255)

    metadata = models.JSONField(default=dict)

    def __str__(self):
        return str(self.client_timestamp) + " - " + str(self.metadata)

    def get_string(self, template: Optional[str] = None) -> str:
        if template is None:
            return str(self)
        return template.format(**self.metadata)

    class Meta:
        indexes = [
            models.Index(fields=["resource_content_type", "resource_id"]),
        ]
