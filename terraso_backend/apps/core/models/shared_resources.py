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
import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class SharedResource(BaseModel):
    """
    This model represents a shared resource.
    Source represents the resource that is being shared (Example: DataEntry).
    Target represents the resource that is receiving the shared resource (Example: Landscape).
    """

    SHARE_ACCESS_NONE = "no"
    SHARE_ACCESS_ALL = "all"
    SHARE_ACCESS_TARGET_MEMBERS = "target_members"
    DEFAULT_SHARE_ACCESS = SHARE_ACCESS_NONE

    SHARE_ACCESS_TYPES = (
        (SHARE_ACCESS_NONE, _("No share access")),
        (SHARE_ACCESS_ALL, _("Anyone with the link")),
        (SHARE_ACCESS_TARGET_MEMBERS, _("Only target members")),
    )

    source = GenericForeignKey("source_content_type", "source_object_id")
    source_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name="source_content_type"
    )
    source_object_id = models.UUIDField()

    target = GenericForeignKey("target_content_type", "target_object_id")
    target_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name="target_content_type"
    )
    target_object_id = models.UUIDField()
    share_uuid = models.UUIDField(default=uuid.uuid4)
    share_access = models.CharField(
        max_length=32,
        choices=SHARE_ACCESS_TYPES,
        default=DEFAULT_SHARE_ACCESS,
    )

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("share_uuid",),
                condition=models.Q(deleted_at__isnull=True),
                name="unique_share_uuid",
            ),
        )

    @classmethod
    def get_share_access_from_text(cls, share_access):
        if not share_access:
            return cls.SHARE_ACCESS_NONE
        lowered = share_access.lower()
        if lowered == cls.SHARE_ACCESS_ALL:
            return cls.SHARE_ACCESS_ALL
        if lowered == cls.SHARE_ACCESS_TARGET_MEMBERS:
            return cls.SHARE_ACCESS_TARGET_MEMBERS
        return cls.SHARE_ACCESS_NONE
