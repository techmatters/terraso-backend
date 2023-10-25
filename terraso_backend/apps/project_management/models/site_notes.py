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

from django.db import models

from apps.core.models import User
from apps.core.models.commons import BaseModel
from apps.project_management import permission_rules


class SiteNote(models.Model):
    class Meta(BaseModel.Meta):
        abstract = False
        rules_permissions = {
            "change": permission_rules.allowed_to_update_site,
            "delete": permission_rules.allowed_to_delete_site,
            "transfer": permission_rules.allowed_to_transfer_site_to_project,
        }

    site = models.ForeignKey('sites.Site', on_delete=models.CASCADE, related_name='notes')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        verbose_name="owner to which the note belongs",
    )
