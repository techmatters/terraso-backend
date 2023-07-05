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
from django.utils.translation import gettext_lazy as _

from apps.core.models import Group, User
from apps.core.models.commons import BaseModel
from apps.project_management import permission_rules


class ProjectSettings(BaseModel):
    class Meta(BaseModel.Meta):
        abstract = False

    member_can_edit_site = models.BooleanField(default=False)
    member_can_add_site_to_project = models.BooleanField(default=False)


class Project(BaseModel):
    class Meta(BaseModel.Meta):
        abstract = False

        rules_permissions = {
            "change": permission_rules.allowed_to_change_project,
            "delete": permission_rules.allowed_to_delete_project,
            "add": permission_rules.allowed_to_add_to_project,
            "add_site": permission_rules.allowed_to_add_site_to_project,
            "archive": permission_rules.allowed_to_archive_project,
        }

    PRIVATE = "private"
    PUBLIC = "public"
    DEFAULT_PRIVACY_STATUS = PRIVATE

    PRIVACY_STATUS = ((PRIVATE, _("Private")), (PUBLIC, _("Public")))

    name = models.CharField(max_length=200)
    group = models.OneToOneField(Group, on_delete=models.CASCADE)
    privacy = models.CharField(
        max_length=32, choices=PRIVACY_STATUS, default=DEFAULT_PRIVACY_STATUS
    )

    @staticmethod
    def default_settings():
        settings = ProjectSettings()
        settings.save()
        return settings

    settings = models.OneToOneField(
        ProjectSettings, on_delete=models.PROTECT, default=default_settings
    )

    archived = models.BooleanField(default=False,)

    @staticmethod
    def create_default_group(name: str):
        """Creates a default group for a project"""
        return Group.objects.create(
            name=name,
            membership_type=Group.MEMBERSHIP_TYPE_OPEN,
            enroll_method=Group.ENROLL_METHOD_INVITE,
        )

    def is_manager(self, user: User) -> bool:
        return self.managers.filter(id=user.id).exists()

    def is_member(self, user: User) -> bool:
        return self.members.filter(id=user.id).exists()

    @property
    def managers(self):
        return self.group.group_managers

    @property
    def members(self):
        return self.group.group_members

    def add_manager(self, user: User):
        return self.group.add_manager(user)

    def add_member(self, user: User):
        return self.group.add_member(user)
