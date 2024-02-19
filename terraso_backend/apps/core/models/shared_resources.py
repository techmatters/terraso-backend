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

from django.conf import settings
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

    SHARE_ACCESS_ALL = "all"
    SHARE_ACCESS_MEMBERS = "members"
    DEFAULT_SHARE_ACCESS = SHARE_ACCESS_MEMBERS

    SHARE_ACCESS_TYPES = (
        (SHARE_ACCESS_ALL, _("Anyone with the link")),
        (SHARE_ACCESS_MEMBERS, _("Only members")),
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

    def get_download_url(self):
        return f"{settings.API_ENDPOINT}/shared-data/download/{self.share_uuid}"

    def get_share_url(self):
        from apps.core.models import Group, Landscape

        target = self.target
        entity = (
            "groups"
            if isinstance(target, Group)
            else "landscapes" if isinstance(target, Landscape) else None
        )
        if not entity:
            return None
        slug = target.slug
        share_uuid = self.share_uuid
        return f"{settings.WEB_CLIENT_URL}/{entity}/{slug}/download/{share_uuid}"

    @classmethod
    def get_share_access_from_text(cls, share_access):
        if not share_access:
            return cls.SHARE_ACCESS_MEMBERS
        lowered = share_access.lower()
        if lowered == cls.SHARE_ACCESS_ALL:
            return cls.SHARE_ACCESS_ALL
        return cls.SHARE_ACCESS_MEMBERS
