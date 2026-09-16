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
from importlib import resources

import pytest

from apps.core.gis.parsers import parse_file_to_geojson

KMZ_TEST_FILES = [
    ("resources/gis/kmz_sample_1.kmz", "resources/gis/kmz_sample_1_geojson.json"),
]
KML_TEST_FILES = [
    ("resources/gis/kml_sample_1.kml", "resources/gis/kml_sample_1_geojson.json"),
    ("resources/gis/kml_sample_2.kml", "resources/gis/kml_sample_2_geojson.json"),
    ("resources/gis/kml_sample_3.kml", "resources/gis/kml_sample_3_geojson.json"),
]
SHAPEFILE_TEST_FILES = [
    ("resources/gis/shapefile_sample_1.zip", "resources/gis/shapefile_sample_1_geojson.json"),
    ("resources/gis/shapefile_sample_2.zip", "resources/gis/shapefile_sample_2_geojson.json"),
]

KML_BARE_AMPERSAND = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
	<name>Trail Network</name>
	<Placemark>
		<name>Trail & Bluffs</name>
		<Point>
			<coordinates>-77.95,-1.65,0</coordinates>
		</Point>
	</Placemark>
</Document>
</kml>
"""

KML_PRE_ESCAPED_AMPERSAND = KML_BARE_AMPERSAND.replace("Trail & Bluffs", "Trail &amp; Bluffs")

KML_CDATA_BARE_AMPERSAND = KML_BARE_AMPERSAND.replace(
    "<name>Trail & Bluffs</name>", "<name><![CDATA[Trail & Bluffs]]></name>"
)


@pytest.fixture
def kml_file(request):
    """Write KML content to a named temp file (parse_file_to_geojson needs .name)."""
    contents = request.param
    with tempfile.NamedTemporaryFile(mode="w", suffix=".kml", delete=False) as f:
        f.write(contents)

    yield f.name

    os.unlink(f.name)


@pytest.mark.parametrize("kml_file", [KML_BARE_AMPERSAND], indirect=True)
def test_parse_kml_file_bare_ampersand(kml_file):
    """KML with a bare '&' in <name> parses (bytes-level escape repair)."""
    with open(kml_file, "rb") as file:
        geojson = parse_file_to_geojson(file)

    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) >= 1


@pytest.mark.parametrize("kml_file", [KML_PRE_ESCAPED_AMPERSAND], indirect=True)
def test_parse_kml_file_pre_escaped_ampersand_not_double_escaped(kml_file):
    """KML already using '&amp;' parses; the ampersand survives as '&'."""
    with open(kml_file, "rb") as file:
        geojson = parse_file_to_geojson(file)

    assert len(geojson["features"]) >= 1
    properties = geojson["features"][0]["properties"]
    values = [v for v in properties.values() if isinstance(v, str)]
    assert "Trail & Bluffs" in values
    assert not any("&amp;" in v for v in values)


@pytest.mark.parametrize("kml_file", [KML_CDATA_BARE_AMPERSAND], indirect=True)
def test_parse_kml_file_bare_ampersand_inside_cdata_preserved(kml_file):
    """A bare '&' inside CDATA is literal text: it must NOT be escaped."""
    with open(kml_file, "rb") as file:
        geojson = parse_file_to_geojson(file)

    assert len(geojson["features"]) >= 1
    properties = geojson["features"][0]["properties"]
    values = [v for v in properties.values() if isinstance(v, str)]
    assert "Trail & Bluffs" in values
    assert not any("&amp;" in v for v in values)


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


@pytest.mark.parametrize(
    "file_path_expected",
    SHAPEFILE_TEST_FILES,
)
def test_parse_shapefile(file_path_expected):
    file_path = file_path_expected[0]
    with open(resources.files("tests").joinpath(file_path), "rb") as file:
        shapefile_json = parse_file_to_geojson(file)

    expected_file_path = file_path_expected[1]
    with open(resources.files("tests").joinpath(expected_file_path), "rb") as file:
        expected_json = json.load(file)

    assert json.dumps(shapefile_json) == json.dumps(expected_json)


@pytest.mark.parametrize(
    "kml_file_path_expected",
    KML_TEST_FILES,
)
def test_parse_kml_file(kml_file_path_expected):
    kml_file_path = kml_file_path_expected[0]
    with open(resources.files("tests").joinpath(kml_file_path), "rb") as file:
        kml_json = parse_file_to_geojson(file)

    expected_file_path = kml_file_path_expected[1]
    with open(resources.files("tests").joinpath(expected_file_path), "rb") as file:
        expected_json = json.load(file)

    assert json.dumps(kml_json) == json.dumps(expected_json)


@pytest.mark.parametrize(
    "kmz_file_path_expected",
    KMZ_TEST_FILES,
)
def test_parse_kmz_file(kmz_file_path_expected):
    kmz_file_path = kmz_file_path_expected[0]
    with open(resources.files("tests").joinpath(kmz_file_path), "rb") as file:
        kmz_json = parse_file_to_geojson(file)

    expected_file_path = kmz_file_path_expected[1]
    with open(resources.files("tests").joinpath(expected_file_path), "rb") as file:
        expected_json = json.load(file)

    assert json.dumps(kmz_json) == json.dumps(expected_json)


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
