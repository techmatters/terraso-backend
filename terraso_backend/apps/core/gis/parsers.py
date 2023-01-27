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
import uuid
import zipfile

import geopandas as gpd
from fiona.drvsupport import supported_drivers

from apps.core.gis.utils import DEFAULT_CRS

supported_drivers["KML"] = "rw"


def is_shape_file_extension(file):
    return file.name.endswith(".zip")


def is_kml_file_extension(file):
    return file.name.endswith(".kml")


def is_kmz_file_extension(file):
    return file.name.endswith(".kmz")


def parse_kml_file(file):
    gdf = gpd.read_file(file, driver="KML")
    return json.loads(gdf.to_json())


def parse_kmz_file(file):
    tmp_folder = os.path.join("/tmp", str(uuid.uuid4()))
    with zipfile.ZipFile(file, "r") as zip:
        kml_filenames = [f for f in zip.namelist() if f.endswith(".kml")]

        if not kml_filenames:
            raise ValueError("Invalid kmz file")

        kml_file = zip.extract(kml_filenames[0], tmp_folder)

    gdf = gpd.read_file(kml_file, driver="KML")

    # Delete extracted files
    os.remove(os.path.join(tmp_folder, kml_filenames[0]))
    os.rmdir(tmp_folder)

    return json.loads(gdf.to_json())


def parse_shapefile(file):
    tmp_folder = os.path.join("/tmp", str(uuid.uuid4()))
    with zipfile.ZipFile(file, "r") as zip:
        shp_filenames = [f for f in zip.namelist() if f.endswith(".shp")]
        shx_filenames = [f for f in zip.namelist() if f.endswith(".shx")]
        prj_filenames = [f for f in zip.namelist() if f.endswith(".prj")]

        if not shp_filenames or not shx_filenames or not prj_filenames:
            raise ValueError("Invalid shapefile")

        shp_file = zip.extract(shp_filenames[0], tmp_folder)
        zip.extract(prj_filenames[0], tmp_folder)
        zip.extract(shx_filenames[0], tmp_folder)

    gdf = gpd.read_file(shp_file)
    gdf_transformed = gdf.to_crs(crs=DEFAULT_CRS)

    # Delete extracted files
    os.remove(os.path.join(tmp_folder, shp_filenames[0]))
    os.remove(os.path.join(tmp_folder, shx_filenames[0]))
    os.remove(os.path.join(tmp_folder, prj_filenames[0]))
    os.rmdir(tmp_folder)

    return json.loads(gdf_transformed.to_json())
