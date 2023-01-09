import json
import os
import tempfile
import zipfile

import geopandas as gpd
import pytest

from apps.core.gis.parsers import parse_kml_file, parse_shapefile
from apps.core.gis.utils import DEFAULT_CRS


@pytest.fixture
def shapefile_zip(request):
    shp, shx, prj = request.param
    zip_file = tempfile.NamedTemporaryFile(suffix=".zip")

    with zipfile.ZipFile(zip_file.name, "w") as zf:
        zf.writestr("test.shp", shp)
        zf.writestr("test.shx", shx)
        zf.writestr("test.prj", prj)

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

        # Parse the Shapefile
        shapefile_json = parse_shapefile(shapefile_zip.name)

        # Verify that the parsed Shapefile is equivalent to the original GeoDataFrame
        assert shapefile_json == json.loads(gdf.to_json())


@pytest.fixture
def kml_file(request):
    kml_contents, file_extension = request.param
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=f".{file_extension}", delete=False) as f:
        # Write the KML content to the file
        f.write(kml_contents)

    # Return the file path
    yield f.name

    # Clean up: delete the temporary file
    os.unlink(f.name)


@pytest.mark.parametrize(
    "kml_file",
    [
        (
            """<?xml version="1.0" encoding="utf-8"?>
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
              </kml>""",
            "kml",
        ),
    ],
    indirect=True,
)
def test_parse_kml_file(kml_file):
    # Call the parse_kml_file function with the file path
    kml_json = parse_kml_file(kml_file)

    # Assert that the output of the parse_kml_file function is as expected
    assert kml_json == {
        "type": "FeatureCollection",
        "features": [
            {
                "id": "0",
                "type": "Feature",
                "properties": {"Name": "Portland", "Description": ""},
                "geometry": {"type": "Point", "coordinates": [-122.681944, 45.52, 0.0]},
            },
            {
                "id": "1",
                "type": "Feature",
                "properties": {"Name": "Rio de Janeiro", "Description": ""},
                "geometry": {"type": "Point", "coordinates": [-43.196389, -22.908333, 0.0]},
            },
            {
                "id": "2",
                "type": "Feature",
                "properties": {"Name": "Istanbul", "Description": ""},
                "geometry": {"type": "Point", "coordinates": [28.976018, 41.01224, 0.0]},
            },
            {
                "id": "3",
                "type": "Feature",
                "properties": {"Name": "Reykjavik", "Description": ""},
                "geometry": {"type": "Point", "coordinates": [-21.933333, 64.133333, 0.0]},
            },
            {
                "id": "4",
                "type": "Feature",
                "properties": {"Name": "Simple Polygon", "Description": ""},
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
