# Copyright © 2026 Technology Matters
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

import enum

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from apps.core.models import User
from apps.core.models.commons import BaseModel

from .sites import Site


class JSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, enum.Enum):
            return obj.value
        return super().default(obj)


# NOTE: this table may contain data associated with sites that was submitted
#       by unauthorized (but still authenticated) users. such requests may have
#       an update_failure_reason of null or "NOT_ALLOWED". unless a user is
#       handcrafting malicious requests, this will be because a user had
#       authorization to edit a site, then went offline and made changes
#       simultaneous to losing authorization for that site.
class SitePushHistory(BaseModel):
    class Meta(BaseModel.Meta):
        verbose_name_plural = "History: SitePushHistory"

    site = models.ForeignKey(Site, null=True, on_delete=models.CASCADE)
    changed_by = models.ForeignKey(User, on_delete=models.CASCADE)
    update_succeeded = models.BooleanField(null=False, blank=False, default=False)
    update_failure_reason = models.TextField(null=True)

    # intended JSON schema: {
    #   "is_new": bool,
    #   "name": str | null,
    #   "latitude": float | null,
    #   "longitude": float | null,
    #   "elevation": float | null,
    #   "privacy": str | null,
    #   "project_id": str | null,
    #   "new_notes": [{"id": str, "content": str}],
    #   "updated_notes": [{"id": str, "content": str}],
    #   "deleted_note_ids": [str]
    # }
    site_changes = models.JSONField(encoder=JSONEncoder)
