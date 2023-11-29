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

import json
import os
import tempfile
import zipfile
from importlib import resources

import geopandas as gpd
import pytest

from apps.core.gis.parsers import parse_file_to_geojson
from apps.core.gis.utils import DEFAULT_CRS

KML_CONTENT = """<?xml version="1.0" encoding="utf-8"?>
              <kml xmlns="http://www.opengis.net/kml/2.2">
                <Document>
                  <Placemark>
                    <name>Portland</name>
                    <Point>
                      <coordinates>-122.681944,45.52,0</coordinates>
                    </Point>
                  </Placemark>
                  <Placemark>
                    <name>Rio de Janeiro</name>
                    <Point>
                      <coordinates>-43.196389,-22.908333,0</coordinates>
                    </Point>
                  </Placemark>
                  <Placemark>
                    <name>Istanbul</name>
                    <Point>
                      <coordinates>28.976018,41.01224,0</coordinates>
                    </Point>
                  </Placemark>
                  <Placemark>
                    <name>Reykjavik</name>
                    <Point>
                      <coordinates>-21.933333,64.133333,0</coordinates>
                    </Point>
                  </Placemark>
                  <Placemark>
                    <name>Simple Polygon</name>
                    <Polygon>
                      <outerBoundaryIs>
                        <LinearRing>
                          <coordinates>-122.681944,45.52,0
                          -43.196389,-22.908333,0
                          28.976018,41.01224,0
                          -21.933333,64.133333,0
                          -122.681944,45.52,0</coordinates>
                        </LinearRing>
                      </outerBoundaryIs>
                    </Polygon>
                  </Placemark>
                </Document>
              </kml>"""

GPX_CONTENT = """<?xml version="1.0" standalone="yes"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1"
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">
    <wpt lat="45.52" lon="-122.681944">
        <ele>0</ele>
        <name><![CDATA[Portland]]></name>
        <cmt><![CDATA[Waypoint no: 1]]></cmt>
        <desc><![CDATA[This is waypoint no: 1]]></desc>
    </wpt>
    <wpt lat="-22.908333" lon="-43.196389">
        <ele>0</ele>
        <name><![CDATA[Rio de Janeiro]]></name>
        <cmt><![CDATA[Waypoint no: 2]]></cmt>
        <desc><![CDATA[This is waypoint no: 2]]></desc>
    </wpt>
    <wpt lat="41.01224" lon="28.976018">
        <ele>0</ele>
        <name><![CDATA[Istanbul]]></name>
        <cmt><![CDATA[Waypoint no: 3]]></cmt>
        <desc><![CDATA[This is waypoint no: 3]]></desc>
    </wpt>
    <wpt lat="64.133333" lon="-21.933333">
        <ele>0</ele>
        <name><![CDATA[Reykjavik]]></name>
        <cmt><![CDATA[Waypoint no: 4]]></cmt>
        <desc><![CDATA[This is waypoint no: 4]]></desc>
    </wpt>
</gpx>"""

KML_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"Name": "Portland"},
            "geometry": {"type": "Point", "coordinates": [-122.681944, 45.52, 0.0]},
        },
        {
            "type": "Feature",
            "properties": {"Name": "Rio de Janeiro"},
            "geometry": {"type": "Point", "coordinates": [-43.196389, -22.908333, 0.0]},
        },
        {
            "type": "Feature",
            "properties": {"Name": "Istanbul"},
            "geometry": {"type": "Point", "coordinates": [28.976018, 41.01224, 0.0]},
        },
        {
            "type": "Feature",
            "properties": {"Name": "Reykjavik"},
            "geometry": {"type": "Point", "coordinates": [-21.933333, 64.133333, 0.0]},
        },
        {
            "type": "Feature",
            "properties": {"Name": "Simple Polygon"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-122.681944, 45.52, 0.0],
                        [-43.196389, -22.908333, 0.0],
                        [28.976018, 41.01224, 0.0],
                        [-21.933333, 64.133333, 0.0],
                        [-122.681944, 45.52, 0.0],
                    ]
                ],
            },
        },
    ],
}

GPX_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "id": "0",
            "type": "Feature",
            "properties": {
                "ele": 0.0,
                "time": None,
                "magvar": None,
                "geoidheight": None,
                "name": "Portland",
                "cmt": "Waypoint no: 1",
                "desc": "This is waypoint no: 1",
                "src": None,
                "link1_href": None,
                "link1_text": None,
                "link1_type": None,
                "link2_href": None,
                "link2_text": None,
                "link2_type": None,
                "sym": None,
                "type": None,
                "fix": None,
                "sat": None,
                "hdop": None,
                "vdop": None,
                "pdop": None,
                "ageofdgpsdata": None,
                "dgpsid": None,
            },
            "geometry": {"type": "Point", "coordinates": [-122.681944, 45.52]},
        },
        {
            "id": "1",
            "type": "Feature",
            "properties": {
                "ele": 0.0,
                "time": None,
                "magvar": None,
                "geoidheight": None,
                "name": "Rio de Janeiro",
                "cmt": "Waypoint no: 2",
                "desc": "This is waypoint no: 2",
                "src": None,
                "link1_href": None,
                "link1_text": None,
                "link1_type": None,
                "link2_href": None,
                "link2_text": None,
                "link2_type": None,
                "sym": None,
                "type": None,
                "fix": None,
                "sat": None,
                "hdop": None,
                "vdop": None,
                "pdop": None,
                "ageofdgpsdata": None,
                "dgpsid": None,
            },
            "geometry": {"type": "Point", "coordinates": [-43.196389, -22.908333]},
        },
        {
            "id": "2",
            "type": "Feature",
            "properties": {
                "ele": 0.0,
                "time": None,
                "magvar": None,
                "geoidheight": None,
                "name": "Istanbul",
                "cmt": "Waypoint no: 3",
                "desc": "This is waypoint no: 3",
                "src": None,
                "link1_href": None,
                "link1_text": None,
                "link1_type": None,
                "link2_href": None,
                "link2_text": None,
                "link2_type": None,
                "sym": None,
                "type": None,
                "fix": None,
                "sat": None,
                "hdop": None,
                "vdop": None,
                "pdop": None,
                "ageofdgpsdata": None,
                "dgpsid": None,
            },
            "geometry": {"type": "Point", "coordinates": [28.976018, 41.01224]},
        },
        {
            "id": "3",
            "type": "Feature",
            "properties": {
                "ele": 0.0,
                "time": None,
                "magvar": None,
                "geoidheight": None,
                "name": "Reykjavik",
                "cmt": "Waypoint no: 4",
                "desc": "This is waypoint no: 4",
                "src": None,
                "link1_href": None,
                "link1_text": None,
                "link1_type": None,
                "link2_href": None,
                "link2_text": None,
                "link2_type": None,
                "sym": None,
                "type": None,
                "fix": None,
                "sat": None,
                "hdop": None,
                "vdop": None,
                "pdop": None,
                "ageofdgpsdata": None,
                "dgpsid": None,
            },
            "geometry": {"type": "Point", "coordinates": [-21.933333, 64.133333]},
        },
    ],
}


@pytest.fixture
def shapefile_zip(request):
    shp, shx, prj = request.param
    zip_file = tempfile.NamedTemporaryFile(suffix=".zip")
    return zip_file


@pytest.mark.parametrize(
    "shapefile_zip",
    [
        (b"<shapefile component 1>", b"<shapefile component 2>", b"<shapefile component 3>"),
        (b"<shapefile component 4>", b"<shapefile component 5>", b"<shapefile component 6>"),
    ],
    indirect=True,
)
def test_parse_shapefile(shapefile_zip):
    # Create a GeoDataFrame with a single point
    gdf = gpd.GeoDataFrame({"geometry": gpd.points_from_xy([0], [0])}, crs=DEFAULT_CRS)

    # Convert the GeoDataFrame to a Shapefile
    with tempfile.TemporaryDirectory() as tmpdir:
        shapefile_path = os.path.join(tmpdir, "test.shp")
        gdf.to_file(shapefile_path)

        # Zip the Shapefile components
        with zipfile.ZipFile(shapefile_zip.name, "w") as zf:
            for component in ["shp", "shx", "prj"]:
                zf.write(os.path.join(tmpdir, f"test.{component}"), f"test.{component}")

        with open(shapefile_zip.name, "rb") as file:
            shapefile_json = parse_file_to_geojson(file)

            # Verify that the parsed Shapefile is equivalent to the original GeoDataFrame
            gdf_json = json.loads(gdf.to_json())
            assert shapefile_json == gdf_json


# @pytest.fixture
# def kml_file(request):
#     kml_contents, file_extension = request.param
#     # Create a temporary file
#     with tempfile.NamedTemporaryFile(mode="w", suffix=f".{file_extension}", delete=False) as f:
#         # Write the KML content to the file
#         f.write(kml_contents)

#     # Return the file path
#     yield f.name

#     # Clean up: delete the temporary file
#     os.unlink(f.name)


@pytest.mark.parametrize(
    "kml_file_path_expected",
    [
        ("resources/gis/kml_sample_1.kml", "resources/gis/kml_sample_1_geojson.json"),
        # ("resources/gis/kml_sample_2.kml", "resources/gis/kml_sample_2_geojson.json"),
    ],
)
def test_parse_kml_file(kml_file_path_expected):
    kml_file_path = kml_file_path_expected[0]
    with open(resources.files("tests").joinpath(kml_file_path), "rb") as file:
        kml_json = parse_file_to_geojson(file)

    expected_file_path = kml_file_path_expected[1]
    with open(resources.files("tests").joinpath(expected_file_path), "rb") as file:
        expected_json = json.load(file)

    # Assert that the output of the parse_kml_file function is as expected
    assert kml_json == KML_GEOJSON
    print(f"kml_json: {json.dumps(kml_json)}")
    print(f"expected_json: {json.dumps(expected_json)}")

    assert json.dumps(kml_json) == json.dumps(expected_json)


@pytest.fixture
def gpx_file(request):
    gpx_contents, file_extension = request.param
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=f".{file_extension}", delete=False) as f:
        # Write the GPX content to the file
        f.write(gpx_contents)

    # Return the file path
    yield f.name

    # Clean up: delete the temporary file
    os.unlink(f.name)


@pytest.mark.parametrize(
    "gpx_file",
    [
        (GPX_CONTENT, "gpx"),
    ],
    indirect=True,
)
def test_parse_gpx_file(gpx_file):
    with open(gpx_file, "rb") as file:
        gpx_json = parse_file_to_geojson(file)

    # Assert that the output of the parse_gpx_file function is as expected
    assert gpx_json == GPX_GEOJSON
