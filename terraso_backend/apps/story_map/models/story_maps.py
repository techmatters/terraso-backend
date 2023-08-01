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

from apps.collaboration.models import MembershipList
from apps.core.models import BaseModel, SlugModel, User
from apps.core.models.commons import validate_name
from apps.story_map import permission_rules as perm_rules


class StoryMap(SlugModel):
    # Story map will not be deleted in cascade, there are S3 resources linked to it.
    # if eventuall we support user account hard deletion we will need to implement a
    # custom delete method for S3 resources.
    _safedelete_policy = SOFT_DELETE

    story_map_id = models.CharField(max_length=10, default="")
    title = models.CharField(max_length=128, validators=[validate_name])
    configuration = models.JSONField(blank=True, null=True)
    created_by = models.ForeignKey(User, null=True, on_delete=models.DO_NOTHING)
    is_published = models.BooleanField(blank=True, default=False)
    published_at = models.DateTimeField(blank=True, null=True)

    membership_list = models.ForeignKey(
        MembershipList, on_delete=models.CASCADE, related_name="story_map", null=True
    )

    field_to_slug = "title"
    fields_to_trim = ["title"]

    class Meta(BaseModel.Meta):
        constraints = (
            models.UniqueConstraint(
                fields=("slug", "story_map_id"),
                condition=models.Q(deleted_at__isnull=True),
                name="story_map_storymap_unique_active_slug_story_map_id",
            ),
        )
        verbose_name_plural = "Story Maps"
        rules_permissions = {
            "change": perm_rules.allowed_to_change_story_map,
            "delete": perm_rules.allowed_to_delete_story_map,
            "view": perm_rules.allowed_to_view_story_map,
            "save_membership": perm_rules.allowed_to_save_membership,
            "delete_membership": perm_rules.allowed_to_delete_membership,
        }

    def to_dict(self):
        return dict(
            id=str(self.id),
            title=self.title,
            configuration=self.configuration,
            created_by=str(self.created_by.id),
            is_published=self.is_published,
            slug=self.slug,
            story_map_id=self.story_map_id,
        )

    def __str__(self):
        return self.title
