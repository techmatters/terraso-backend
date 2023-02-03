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

import math

from apps.core.gis.utils import (
    calculate_geojson_feature_area,
    calculate_geojson_polygon_area,
)


def test_calculate_area(unit_polygon):
    area = calculate_geojson_polygon_area(unit_polygon)
    assert math.isclose(1.0, area, rel_tol=0.1)


def test_calculate_multipoly(usa_geojson):
    area = calculate_geojson_feature_area(usa_geojson)
    assert math.isclose(9510743744824, area, rel_tol=0.001)
