"""Geospatial utility methods"""
from pyproj import CRS
from shapely.geometry import shape

# CRS that should be used for all GeoJSON (see https://www.rfc-editor.org/rfc/rfc7946#section-4)
DEFAULT_CRS = CRS.from_string("urn:ogc:def:crs:OGC:1.3:CRS84")


def calculate_geojson_feature_area(feature_json):
    try:
        features = feature_json["features"]
        if not features:
            raise ValueError("Boundary is empty!")
        total_area = 0
        for feature in features:
            geom = feature["geometry"]
            if geom["type"] in ("Polygon", "MultiPolygon"):
                total_area += calculate_geojson_polygon_area(geom)
        return total_area
    except KeyError as e:
        # if the JSON is not formed as expected, this will give an easier to understand exception
        raise ValueError(f"Expecting key '{e.args[0]}' in feature JSON, but it was missing")


def calculate_geojson_polygon_area(polygon_json):
    """Calculates the area of a polygon supplied in GeoJSON format. Default CRS is WSG84 if
    none are provided"""
    untransformed = shape(polygon_json)
    geod = DEFAULT_CRS.get_geod()
    area, _perimeter = geod.geometry_area_perimeter(untransformed)
    return abs(area)


def m2_to_hectares(area):
    return area / 10000
