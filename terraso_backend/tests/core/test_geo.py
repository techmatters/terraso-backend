import math

from apps.core.geo import calculate_geojson_feature_area, calculate_geojson_polygon_area


def test_calculate_area(unit_polygon):
    area = calculate_geojson_polygon_area(unit_polygon)
    assert math.isclose(1.0, area, rel_tol=0.1)


def test_calculate_multipoly(usa_geojson):
    area = calculate_geojson_feature_area(usa_geojson)
    assert math.isclose(9510743744824, area, rel_tol=0.001)
