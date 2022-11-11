"""Geospatial utility methods"""
from pyproj import CRS
from shapely.geometry import shape

DEFAULT_CRS = 4326


def calculate_geojson_polygon_area(polygon_json, crs=None):
    """Calculates the area of a polygon supplied in GeoJSON format. Default CRS is WSG84 if
    none are provided"""
    untransformed = shape(polygon_json)
    if not crs:
        crs = CRS(DEFAULT_CRS)
    geod = crs.get_geod()
    area, _perimeter = geod.geometry_area_perimeter(untransformed)
    return abs(area)
