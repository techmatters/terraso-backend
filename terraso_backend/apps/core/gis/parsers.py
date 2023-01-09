import json
import os
import uuid
import zipfile

import geopandas as gpd

from apps.core.gis.utils import DEFAULT_CRS


def isShapefile(file):
    return file.name.endswith(".zip")


def isKmlFile(file):
    return file.name.endswith(".kml") or file.name.endswith(".kmz")


def parseKmlFile(file):
    gdf = gpd.read_file(file)
    return json.loads(gdf.to_json())


def parseShapefile(file):
    tmp_folder = os.path.join("/tmp", str(uuid.uuid4()))
    with zipfile.ZipFile(file, "r") as zip:
        shp_filenames = [f for f in zip.namelist() if f.endswith(".shp")]
        shx_filenames = [f for f in zip.namelist() if f.endswith(".shx")]
        prj_filenames = [f for f in zip.namelist() if f.endswith(".prj")]

        if not shp_filenames or not shx_filenames or not prj_filenames:
            raise ValueError("Invalid shapefile")

        shpFile = zip.extract(shp_filenames[0], tmp_folder)
        zip.extract(prj_filenames[0], tmp_folder)
        zip.extract(shx_filenames[0], tmp_folder)

    gdf = gpd.read_file(shpFile)
    gdf_transformed = gdf.to_crs(crs=DEFAULT_CRS)

    # Delete extracted files
    os.remove(os.path.join(tmp_folder, shp_filenames[0]))
    os.remove(os.path.join(tmp_folder, shx_filenames[0]))
    os.remove(os.path.join(tmp_folder, prj_filenames[0]))
    os.rmdir(tmp_folder)

    return json.loads(gdf_transformed.to_json())
