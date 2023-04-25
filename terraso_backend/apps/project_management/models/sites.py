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

from apps.core import permission_rules
from apps.core.models.commons import SlugModel

from .projects import Project


class Site(SlugModel):
    class Meta(SlugModel.Meta):
        abstract = False

        rules_permissions = {"change": permission_rules.allowed_to_edit_site}

    name = models.CharField(max_length=200)
    name = models.CharField(max_length=200)
    latitude = models.FloatField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    longitude = models.FloatField()

    field_to_slug = "id"
    field_to_slug = "id"

    project = models.ForeignKey(
        Project,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        verbose_name="project to which the site belongs",
    )
