import math

from apps.core.geo import calculate_geojson_polygon_area


def test_calculate_area(unit_polygon):
    area = calculate_geojson_polygon_area(unit_polygon)
    assert math.isclose(1.0, area, rel_tol=0.1)
