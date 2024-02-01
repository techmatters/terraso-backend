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
