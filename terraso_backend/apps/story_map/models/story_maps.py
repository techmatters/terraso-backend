# Copyright © 2021-2023 Technology Matters
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
from safedelete.models import SOFT_DELETE

from apps.core.models import BaseModel, SlugModel, User
from apps.shared_data import permission_rules as perm_rules


class StoryMap(SlugModel):
    # file will not be deleted in cascade
    _safedelete_policy = SOFT_DELETE

    title = models.CharField(max_length=128)
    configuration = models.JSONField(blank=True, null=True)
    created_by = models.ForeignKey(User, null=True, on_delete=models.DO_NOTHING)
    is_published = models.BooleanField(blank=True, default=False)

    field_to_slug = "title"
    fields_to_trim = ["title"]

    class Meta(BaseModel.Meta):
        verbose_name_plural = "Story Maps"
        rules_permissions = {
            "change": perm_rules.allowed_to_change_story_map,
            "delete": perm_rules.allowed_to_delete_story_map,
            "view": perm_rules.allowed_to_view_story_map,
        }
        _unique_fields = ["slug"]

    def to_dict(self):
        return dict(
            id=str(self.id),
            title=self.title,
            is_published=self.is_published,
            slug=self.slug,
        )

    def __str__(self):
        return self.title
