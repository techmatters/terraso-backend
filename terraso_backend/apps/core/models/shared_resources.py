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
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.core.models import BaseModel


class SharedResource(BaseModel):
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
