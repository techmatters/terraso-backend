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
from apps.core.models import User
from apps.core.models.commons import BaseModel, SlugModel


class Project(BaseModel):
    class Meta(BaseModel.Meta):
        abstract = False

        rules_permissions = {"add_site": permission_rules.can_add_site}

    PRIVATE = "pri"
    PUBLIC = "pub"
    PRIVACY_OPTIONS = [(PRIVATE, "Private"), (PUBLIC, "Public")]

    name = models.CharField(max_length=200)
    privacy = models.CharField(max_length=3, choices=PRIVACY_OPTIONS, default=PRIVATE)
    members = models.ManyToManyField(User, through="ProjectMembership")

    def is_manager(self, user):
        return ProjectMembership.objects.filter(
            member=user, project=self, membership=ProjectMembership.MANAGER
        ).exists()


class Site(SlugModel):
    class Meta(SlugModel.Meta):
        abstract = False

        rules_permissions = {"add_to_project": permission_rules.is_site_creator}

    name = models.CharField(max_length=200)
    latitude = models.FloatField()
    longitude = models.FloatField()

    field_to_slug = "id"

    # note: for now, do not allow user account deletion if they have sites
    creator = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="creator of site")
    project = models.ForeignKey(
        Project,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="project to which the site belongs",
    )


class ProjectMembership(models.Model):
    MANAGER = "mang"
    MEMBER = "memb"
    MEMBERSHIP_TYPE = [(MANAGER, "Manager"), (MEMBER, "Member")]

    membership = models.CharField(max_length=4, choices=MEMBERSHIP_TYPE, default=MEMBER)
    member = models.ForeignKey(User, on_delete=models.CASCADE, related_name="projects")
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
