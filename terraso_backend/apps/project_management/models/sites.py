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
from typing import Self, Union

from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.models import Membership, User
from apps.core.models.commons import BaseModel
from apps.project_management import permission_rules

from .projects import Project


class Site(BaseModel):
    class Meta(BaseModel.Meta):
        abstract = False
        constraints = [
            models.CheckConstraint(
                check=(models.Q(project__isnull=False) | models.Q(owner__isnull=False))
                & (models.Q(project__isnull=True) | models.Q(owner__isnull=True)),
                name="site_must_be_owned_once",
            )
        ]
        rules_permissions = {
            "change": permission_rules.allowed_to_update_site,
            "delete": permission_rules.allowed_to_delete_site,
            "transfer": permission_rules.allowed_to_transfer_site_to_project,
        }

    name = models.CharField(max_length=200)
    latitude = models.FloatField()
    longitude = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        verbose_name="owner to which the site belongs",
    )

    seen_by = models.ManyToManyField(User, related_name="+")

    PRIVATE = "private"
    PUBLIC = "public"
    DEFAULT_PRIVACY_STATUS = PRIVATE

    PRIVACY_STATUS = ((PRIVATE, _("Private")), (PUBLIC, _("Public")))

    privacy = models.CharField(
        max_length=32, null=False, choices=PRIVACY_STATUS, default=DEFAULT_PRIVACY_STATUS
    )

    project = models.ForeignKey(
        Project,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        verbose_name="project to which the site belongs",
    )

    archived = models.BooleanField(
        default=False,
    )

    @property
    def owned_by_user(self):
        return self.owner is not None

    def add_to_project(self, project):
        if self.owned_by_user:
            self.owner = None
        self.project = project
        self.save()

    def add_owner(self, user):
        if not self.owned_by_user:
            self.project = None
        self.owner = user
        self.save()

    def owned_by(self, obj: Union[Project, User]):
        return obj == self.owner or obj == self.project

    def human_readable(self) -> str:
        return self.name

    def mark_seen_by(self, user: User):
        self.seen_by.add(user)

    @classmethod
    def bulk_change_project(cls, sites: [Self], project: Project):
        for site in sites:
            site.owner = None
            site.project = project
        return Site.objects.bulk_update(sites, ["owner", "project"])


def filter_only_sites_user_owner_or_member(user: User, queryset):
    return queryset.filter(
        Q(owner=user)
        | Q(
            project__membership_list__memberships__user=user,
            project__membership_list__memberships__membership_status=Membership.APPROVED,
        )
    )
