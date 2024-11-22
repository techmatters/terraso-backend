# Copyright © 2024 Technology Matters
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

from apps.core.models.commons import BaseModel
from apps.project_management.models.sites import Site


class SoilMetadata(BaseModel):
    site = models.OneToOneField(Site, on_delete=models.CASCADE, related_name="soil_metadata")

    # upcoming work will support multiple soil ID ratings, but for now there's only one value
    selected_soil_id = models.CharField(blank=True, null=True)

    class Meta(BaseModel.Meta):
        verbose_name_plural = "soil metadata"
