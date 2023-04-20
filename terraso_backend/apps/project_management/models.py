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

from apps.core import permission_rules
from apps.core.models import Group, Membership, User
from apps.core.models.commons import BaseModel, SlugModel


class Project(BaseModel):
    class Meta(BaseModel.Meta):
        abstract = False

        rules_permissions = {"change": permission_rules.allowed_to_change_project}

    name = models.CharField(max_length=200)
    group = models.OneToOneField(Group, on_delete=models.CASCADE)

    def is_manager(self, user: User) -> bool:
        return self.managers.filter(id=user.id).exists()

    def is_member(self, user: User) -> bool:
        return self.members.filter(id=user.id).exists()

    @property
    def managers(self):
        manager_memberships = models.Subquery(
            self.group.memberships.managers_only().values("user_id")
        )
        return User.objects.filter(id__in=manager_memberships)

    @property
    def members(self):
        member_memberships = models.Subquery(
            self.group.memberships.approved_only()
            .filter(user_role=Membership.ROLE_MEMBER)
            .values("user_id")
        )
        return User.objects.filter(id__in=member_memberships)

    def add_manager(self, user: User):
        return self.group.add_manager(user)

    def add_member(self, user: User):
        return self.group.add_member(user)


class Site(SlugModel):
    class Meta(SlugModel.Meta):
        abstract = False

        rules_permissions = {"change": permission_rules.allowed_to_edit_site}

    name = models.CharField(max_length=200)
    latitude = models.FloatField()
    longitude = models.FloatField()

    field_to_slug = "id"

    project = models.ForeignKey(
        Project,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        verbose_name="project to which the site belongs",
    )
