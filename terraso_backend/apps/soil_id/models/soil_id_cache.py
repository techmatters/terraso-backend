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
from soil_id.us_soil import SoilListOutputData

from apps.core.models.commons import BaseModel


class SoilIdCache(BaseModel):
    latitude = models.FloatField()
    longitude = models.FloatField()
    failure_reason = models.TextField(null=True)
    soil_list_json = models.JSONField(null=True)
    rank_data_csv = models.TextField(null=True)
    map_unit_component_data_csv = models.TextField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["latitude", "longitude"], name="coordinate_index")
        ]
        verbose_name = "Soil ID Cache"
        verbose_name_plural = "Soil ID Cache"

    @classmethod
    def round_coordinate(cls, coord: float):
        return round(coord, 6)

    @classmethod
    def save_data(cls, latitude: float, longitude: float, data: SoilListOutputData | str):
        if isinstance(data, str):
            data_to_save = {"failure_reason": data}
        else:
            data_to_save = {
                "soil_list_json": data.soil_list_json,
                "rank_data_csv": data.rank_data_csv,
                "map_unit_component_data_csv": data.map_unit_component_data_csv,
            }

        cls.objects.update_or_create(
            latitude=cls.round_coordinate(latitude),
            longitude=cls.round_coordinate(longitude),
            defaults=data_to_save,
        )

    @classmethod
    def get_data(cls, latitude: float, longitude: float) -> SoilListOutputData | str:
        try:
            prev_result = cls.objects.get(
                latitude=cls.round_coordinate(latitude), longitude=cls.round_coordinate(longitude)
            )
            if prev_result.failure_reason is not None:
                return prev_result.failure_reason

            return SoilListOutputData(
                soil_list_json=prev_result.soil_list_json,
                rank_data_csv=prev_result.rank_data_csv,
                map_unit_component_data_csv=prev_result.map_unit_component_data_csv,
            )
        except cls.DoesNotExist:
            return None
