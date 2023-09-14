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
from typing import Literal, Optional

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.collaboration.models import Membership, MembershipList
from apps.core.models import User
from apps.core.models.commons import BaseModel
from apps.project_management import permission_rules


class ProjectSettings(BaseModel):
    class Meta(BaseModel.Meta):
        abstract = False

    member_can_update_site = models.BooleanField(default=False)
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

    ROLES = ("viewer", "contributor", "manager")

    PRIVATE = "private"
    PUBLIC = "public"
    DEFAULT_PRIVACY_STATUS = PRIVATE

    PRIVACY_STATUS = ((PRIVATE, _("Private")), (PUBLIC, _("Public")))

    name = models.CharField(max_length=200)
    description = models.CharField(max_length=512, default="", blank=True)
    membership_list = models.OneToOneField(MembershipList, on_delete=models.CASCADE)
    privacy = models.CharField(
        max_length=32, choices=PRIVACY_STATUS, default=DEFAULT_PRIVACY_STATUS
    )

    @staticmethod
    def default_settings():
        settings = ProjectSettings()
        settings.save()
        return settings

    settings = models.OneToOneField(ProjectSettings, on_delete=models.PROTECT)

    # overriding save to ensure we have a group and settings
    def save(self, *args, **kwargs):
        if not hasattr(self, "settings"):
            self.settings = self.default_settings()
        if not hasattr(self, "membership_list"):
            self.membership_list = self.create_membership_list()
        return super(Project, self).save(*args, **kwargs)

    archived = models.BooleanField(
        default=False,
    )

    @staticmethod
    def create_membership_list() -> MembershipList:
        """Creates a default group for a project"""
        return MembershipList.objects.create(
            membership_type=MembershipList.MEMBERSHIP_TYPE_OPEN,
            enroll_method=MembershipList.ENROLL_METHOD_JOIN,
        )

    @classmethod
    def create_project(
        cls,
        user: User,
        name: str,
        description: Optional[str],
        privacy: Literal["private", "public"],
    ):
        membership_list = cls.create_membership_list()
        Membership.objects.create(
            membership_list=membership_list, user=user, user_role="MANAGER", pending_email=None
        )
        return cls.objects.create(name=name, description=description, privacy=privacy)

    def is_manager(self, user: User) -> bool:
        return self.managers.filter(id=user.id).exists()

    def is_viewer(self, user: User) -> bool:
        return self.viewers.filter(id=user.id).exists()

    def is_contributor(self, user: User) -> bool:
        return self.contributors.filter(id=user.id).exists()

    @property
    def manager_memberships(self):
        return self.membership_list.memberships.by_role("MANAGER")

    @property
    def viewer_memberships(self):
        return self.membership_list.memberships.by_role("VIEWER")

    @property
    def contributor_memberships(self):
        return self.membership_list.memberships.by_role("CONTRIBUTOR")

    def add_manager(self, user: User):
        return Membership.objects.create(
            membership_list=self.membership_list,
            user=user,
            membership_status=Membership.APPROVED,
            user_role="MANAGER",
            pending_email=None,
        )

    def get_membership(self, user: User):
        return self.membership_list.memberships.filter(user=user).first()

    def __str__(self):
        return self.name
