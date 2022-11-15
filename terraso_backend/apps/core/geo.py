"""Geospatial utility methods"""
from pyproj import CRS
from shapely.geometry import shape

# CRS that should be used for all GeoJSON (see https://www.rfc-editor.org/rfc/rfc7946#section-4)
DEFAULT_CRS = CRS.from_string("urn:ogc:def:crs:OGC:1.3:CRS84")


def calculate_geojson_feature_area(feature_json):
    try:
        crs = DEFAULT_CRS
        features = feature_json["features"]
        if len(features) != 1:
            raise ValueError(f"Expecting only 1 feature, but saw {len(features)}")
        feature = features[0]
        geom = feature["geometry"]
        if geom["type"] == "Polygon":
            return calculate_geojson_polygon_area(geom, crs)
        # if the boundary is not a Polygon, we don't want to return a real area
        return None
    except KeyError as e:
        # if the JSON is not formed as expected, this will give an easier to understand exception
        raise ValueError(f"Expecting key '{e.args[0]}' in feature JSON, but it was missing")


def calculate_geojson_polygon_area(polygon_json, crs=None):
    """Calculates the area of a polygon supplied in GeoJSON format. Default CRS is WSG84 if
    none are provided"""
    untransformed = shape(polygon_json)
    if not crs:
        crs = CRS(DEFAULT_CRS)
    geod = crs.get_geod()
    area, _perimeter = geod.geometry_area_perimeter(untransformed)
    return abs(area)


def m2_to_hectares(area):
    return area / 1000
