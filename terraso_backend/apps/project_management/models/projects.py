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

from apps.core import permission_rules
from apps.core.models import Group, User
from apps.core.models.commons import BaseModel


class Project(BaseModel):
    class Meta(BaseModel.Meta):
        abstract = False

        rules_permissions = {"change": permission_rules.allowed_to_change_project}

    PRIVATE = "private"
    PUBLIC = "public"
    DEFAULT_PRIVACY_STATUS = PRIVATE

    PRIVACY_STATUS = ((PRIVATE, _("Private")), (PUBLIC, _("Public")))

    name = models.CharField(max_length=200)
    group = models.OneToOneField(Group, on_delete=models.CASCADE)
    privacy = models.CharField(
        max_length=32, choices=PRIVACY_STATUS, default=DEFAULT_PRIVACY_STATUS
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
