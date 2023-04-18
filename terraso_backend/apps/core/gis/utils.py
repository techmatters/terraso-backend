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

"""Geospatial utility methods"""
import structlog
from pyproj import CRS
from shapely.geometry import MultiPolygon, shape

logger = structlog.get_logger(__name__)

# CRS that should be used for all GeoJSON (see https://www.rfc-editor.org/rfc/rfc7946#section-4)
DEFAULT_CRS = CRS.from_string("urn:ogc:def:crs:OGC:1.3:CRS84")


def calculate_geojson_centroid(feature_json):
    if not feature_json:
        return None
    try:
        features = feature_json["features"]

        if not features:
            return None

        # If geojson has a Point feature, return the coordinates
        point = next(
            (
                {"lat": geom.get("coordinates")[1], "lng": geom.get("coordinates")[0]}
                for feature in features
                for geom in [feature.get("geometry")]
                if geom and geom.get("type") == "Point"
            ),
            None,
        )
        if point:
            return point

        polygons = [
            shape(feature["geometry"])
            for feature in features
            if feature["geometry"]["type"] == "Polygon"
        ] + [
            shape({"type": "Polygon", "coordinates": polygon})
            for feature in features
            for polygon in feature["geometry"]["coordinates"]
            if feature["geometry"]["type"] == "MultiPolygon"
        ]

        boundary_polygon = MultiPolygon(polygons)

        centroid = boundary_polygon.centroid
        if centroid.is_empty:
            return None
        return {
            "lat": centroid.y,
            "lng": centroid.x,
        }
    except Exception as error:
        logger.exception(
            "Error calculating centroid", extra={"feature_json": feature_json, "error": error}
        )
        return None


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
