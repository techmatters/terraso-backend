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

from apps.core.models import User
from apps.core.models.commons import SlugModel


class Site(SlugModel):
    class Meta(SlugModel.Meta):
        abstract = False
        _unique_fields = ["name"]

    name = models.CharField(max_length=200)
    lat_deg = models.FloatField()
    lon_deg = models.FloatField()

    # note: for now, do not let user account deletion if they have sites
    creator = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="creator of site")

    field_to_slug = "name"
