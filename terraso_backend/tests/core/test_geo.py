import math

from pyproj import CRS, Transformer

from apps.core.geo import DEFAULT_CRS, calculate_geojson_polygon_area


def test_calculate_area():
    center_x, center_y = (1281904.47, 8752400.16)
    xs = [center_x + delta for delta in [0, 0, 1, 1, 0]]
    ys = [center_y + delta for delta in [0, 1, 1, 0, 0]]
    # UTM zone 32S, chosen at random
    source_crs = CRS.from_epsg(9156)
    # Web Mercator
    target_crs = CRS.from_epsg(DEFAULT_CRS)
    proj = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    x_degrees, y_degrees = proj.transform(xs, ys)
    geojson = {
        "type": "Polygon",
        "coordinates": [
            list(zip(x_degrees, y_degrees)),
        ],
    }
    area = calculate_geojson_polygon_area(geojson)
    assert math.isclose(1.0, area, rel_tol=0.1)
