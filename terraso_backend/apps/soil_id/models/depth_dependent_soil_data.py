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

from apps.core.models.commons import BaseModel
from apps.soil_id.models.soil_data_inputs import SoilDataInput


class DepthDependentSoilData(BaseModel):
    soil_data_inputs = models.ForeignKey(SoilDataInput, related_name="depth_dependent_soil_data", on_delete=models.CASCADE)
    depth_top = models.IntegerField(blank=True)
    depth_bottom = models.IntegerField(blank=True)
    conductivity = models.FloatField(blank=True)
    slope = models.IntegerField(blank=True)
