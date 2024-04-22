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

from apps.collaboration.models import Membership, MembershipList
from apps.core.models import User
from apps.core.models.commons import BaseModel
from apps.project_management import permission_rules_old
from apps.project_management.collaboration_roles import ProjectRole


class ProjectSettings(BaseModel):
    """NOTE: Theses settings are currently ignored, and might be removed later"""

    class Meta(BaseModel.Meta):
        abstract = False

    member_can_update_site = models.BooleanField(default=False)
    member_can_add_site_to_project = models.BooleanField(default=False)


class ProjectMembership(Membership):
    """A proxy class created solely for graphene schema reasons"""

    class Meta:
        proxy = True


class ProjectMembershipList(MembershipList):
    """A proxy class created solely for graphql schema reasons"""

    class Meta:
        proxy = True


class Project(BaseModel):
    class Meta(BaseModel.Meta):
        abstract = False

        rules_permissions = {
            "change": permission_rules_old.allowed_to_change_project,
            "delete": permission_rules_old.allowed_to_delete_project,
            "add": permission_rules_old.allowed_to_add_to_project,
            "add_site": permission_rules_old.allowed_to_add_site_to_project,
            "archive": permission_rules_old.allowed_to_archive_project,
        }

    name = models.CharField(max_length=120)
    description = models.CharField(max_length=512, default="", blank=True)
    membership_list = models.OneToOneField(ProjectMembershipList, on_delete=models.CASCADE)

    class MeasurementUnit(models.TextChoices):
        ENGLISH = "ENGLISH"
        METRIC = "METRIC"

    measurement_units = models.CharField(
        choices=MeasurementUnit.choices, default=MeasurementUnit.METRIC.value
    )

    class Privacy(models.TextChoices):
        PRIVATE = "PRIVATE"
        PUBLIC = "PUBLIC"

    privacy = models.CharField(
        max_length=32, choices=Privacy.choices, default=Privacy.PRIVATE.value
    )

    seen_by = models.ManyToManyField(User, related_name="+")
    archived = models.BooleanField(
        default=False,
    )

    settings = models.OneToOneField(ProjectSettings, on_delete=models.PROTECT)

    site_instructions = models.TextField(null=True, blank=True)

    @staticmethod
    def default_settings():
        settings = ProjectSettings()
        settings.save()
        return settings

    # overriding save to ensure we have a group and settings
    def save(self, *args, **kwargs):
        if not hasattr(self, "settings"):
            self.settings = self.default_settings()
        if not hasattr(self, "membership_list"):
            self.membership_list = self.create_membership_list()
        return super(Project, self).save(*args, **kwargs)

    @staticmethod
    def create_membership_list() -> MembershipList:
        """Creates a default group for a project"""
        return ProjectMembershipList.objects.create(
            membership_type=MembershipList.MEMBERSHIP_TYPE_OPEN,
            enroll_method=MembershipList.ENROLL_METHOD_JOIN,
        )

    def user_has_role(self, user: User, role: ProjectRole) -> bool:
        return self.memberships_by_role(role).filter(user=user).exists()

    def is_sole_manager(self, user: User) -> bool:
        return self.is_manager(user) and self.manager_memberships.count() == 1

    def is_manager(self, user: User) -> bool:
        return self.user_has_role(user, ProjectRole.MANAGER)

    def is_contributor(self, user: User) -> bool:
        return self.user_has_role(user, ProjectRole.CONTRIBUTOR)

    def is_viewer(self, user: User) -> bool:
        return self.user_has_role(user, ProjectRole.VIEWER)

    def is_member(self, user: User) -> bool:
        return self.membership_list.is_member(user)

    @property
    def manager_memberships(self):
        return self.memberships_by_role(ProjectRole.MANAGER)

    @property
    def contributor_memberships(self):
        return self.memberships_by_role(ProjectRole.CONTRIBUTOR)

    @property
    def viewer_memberships(self):
        return self.memberships_by_role(ProjectRole.VIEWER)

    def memberships_by_role(self, role: ProjectRole):
        return self.membership_list.memberships.by_role(role.value)

    def add_manager(self, user: User):
        return self.add_user_with_role(user, ProjectRole.MANAGER)

    def add_contributor(self, user: User):
        return self.add_user_with_role(user, ProjectRole.CONTRIBUTOR)

    def add_viewer(self, user: User):
        return self.add_user_with_role(user, ProjectRole.VIEWER)

    def add_user_with_role(self, user: User, role: ProjectRole):
        return Membership.objects.create(
            membership_list=self.membership_list,
            user=user,
            membership_status=Membership.APPROVED,
            user_role=role.value,
            pending_email=None,
        )

    def get_membership(self, user: User):
        return ProjectMembership.objects.filter(
            membership_list=self.membership_list, user=user
        ).first()

    def mark_seen_by(self, user: User):
        self.seen_by.add(user)

    def remove_user(self, user: User):
        membership = self.get_membership(user)
        if membership:
            membership.delete()
        self.save()

    def __str__(self):
        return self.name
