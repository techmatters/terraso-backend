# Copyright © 2023 Technology Matters
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

import csv
import json

import pandas
import structlog
from django.conf import settings
from django.core.files.base import ContentFile

from apps.core.gis.parsers import parse_file_to_geojson
from apps.core.models.groups import Group
from apps.core.models.landscapes import Landscape
from apps.shared_data.services import data_entry_upload_service, geojson_upload_service
from apps.story_map.models.story_maps import StoryMap

from .models import VisualizationConfig

logger = structlog.get_logger(__name__)


def get_rows_from_file(data_entry):
    type = data_entry.resource_type
    if type.startswith("csv"):
        file = data_entry_upload_service.get_file(data_entry.s3_object_name, "rt")
        reader = csv.reader(file)
        return [row for row in reader]
    elif type.startswith("xls"):
        file = data_entry_upload_service.get_file(data_entry.s3_object_name, "rb")
        df = pandas.read_excel(file, dtype=str)
        rows = df.values.tolist()
        return [df.columns.tolist()] + rows
    else:
        raise Exception(
            "Invalid file type for processing data entry",
            extra={"file_type": type, "data_entry_id": data_entry.id},
        )


def get_owner_name(visualization):
    if isinstance(visualization.owner, Landscape):
        return visualization.owner.name
    elif isinstance(visualization.owner, Group):
        return visualization.owner.name
    elif isinstance(visualization.owner, StoryMap):
        return visualization.owner.title
    return "Unknown"


def _get_geojson_from_dataset(data_entry, configuration):
    rows = get_rows_from_file(data_entry)

    first_row = rows[0]

    dataset_config = configuration["datasetConfig"]
    annotate_config = configuration["annotateConfig"]

    longitude_column = dataset_config["longitude"]
    longitude_index = first_row.index(longitude_column)

    latitude_column = dataset_config["latitude"]
    latitude_index = first_row.index(latitude_column)

    data_points = annotate_config["dataPoints"]
    data_points_indexes = [
        {
            "label": data_point.get("label", data_point["column"]),
            "index": first_row.index(data_point["column"]),
        }
        for data_point in data_points
    ]

    annotation_title = annotate_config.get("annotationTitle")

    title_index = (
        first_row.index(annotation_title)
        if annotation_title and annotation_title in first_row
        else None
    )

    features = []
    for row in rows:
        fields = [
            {
                "label": data_point["label"],
                "value": row[data_point["index"]],
            }
            for data_point in data_points_indexes
        ]

        properties = {
            "title": row[title_index] if title_index else None,
            "fields": json.dumps(fields),
        }

        try:
            longitude = float(row[longitude_index])
            latitude = float(row[latitude_index])
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [longitude, latitude],
                },
                "properties": properties,
            }

            features.append(feature)
        except ValueError:
            continue

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def _get_geojson_from_gis(data_entry):
    file = data_entry_upload_service.get_file(data_entry.s3_object_name, "rb")
    return parse_file_to_geojson(file)


def get_geojson_from_data_entry(data_entry, visualization):
    is_dataset = f".{data_entry.resource_type}" in settings.DATA_ENTRY_SPREADSHEET_TYPES.keys()
    is_gis = f".{data_entry.resource_type}" in settings.DATA_ENTRY_GIS_TYPES.keys()

    if is_dataset:
        return _get_geojson_from_dataset(data_entry, visualization.configuration)

    if is_gis:
        return _get_geojson_from_gis(data_entry)


def upload_geojson_to_s3(visualization_id):
    """Upload GeoJSON to S3 for an existing VC (used by Update mutation).

    Unlike upload_geojson_to_s3_precreate, this degrades gracefully:
    if the data entry type has no spatial data, it logs a warning and
    returns None without modifying the VC's current S3 key.
    """
    logger.info("Uploading geojson to S3", visualization_id=visualization_id)
    visualization = VisualizationConfig.objects.get(pk=visualization_id)
    data_entry = visualization.data_entry

    try:
        path = upload_geojson_to_s3_precreate(
            visualization.id, data_entry, visualization.configuration
        )
    except ValueError:
        logger.warning(
            "Skipping S3 upload: data entry type has no spatial data",
            extra={
                "visualization_id": visualization_id,
                "resource_type": data_entry.resource_type,
            },
        )
        return None

    if path is None:
        return None

    # Clean up old S3 key if it exists (after new upload succeeds)
    old_key = visualization.geojson_s3_key
    visualization.geojson_s3_key = path
    visualization.save()

    if old_key:
        try:
            geojson_upload_service.delete_file(old_key)
        except Exception as e:
            logger.warning(
                "Failed to delete old S3 key",
                extra={"key": old_key, "error": str(e)},
            )

    logger.info("Geojson uploaded to S3", visualization_id=visualization_id, key=path)
    return path


def upload_geojson_to_s3_precreate(vc_id, data_entry, configuration):
    """Upload GeoJSON to S3 for a VC that hasn't been created yet.

    Args:
        vc_id: UUID for the VC (used to construct the S3 path)
        data_entry: DataEntry instance
        configuration: dict or JSON string (the VC's configuration field)

    Returns the S3 key, or None if no GeoJSON could be generated.
    Raises on S3 failure (e.g. S3 timeout, credential error).
    """
    config = json.loads(configuration) if isinstance(configuration, str) else configuration

    is_dataset = f".{data_entry.resource_type}" in settings.DATA_ENTRY_SPREADSHEET_TYPES.keys()
    is_gis = f".{data_entry.resource_type}" in settings.DATA_ENTRY_GIS_TYPES.keys()

    if is_dataset:
        geojson = _get_geojson_from_dataset(data_entry, config)
    elif is_gis:
        geojson = _get_geojson_from_gis(data_entry)
    else:
        logger.warning(
            "Cannot generate geojson: data entry type has no spatial data",
            extra={"vc_id": str(vc_id), "resource_type": data_entry.resource_type},
        )
        raise ValueError(
            f"Data entry type '{data_entry.resource_type}' does not contain "
            "spatial data and cannot be used for map visualizations."
        )

    if geojson is None:
        logger.warning(
            "GeoJSON generation returned None",
            extra={"vc_id": str(vc_id)},
        )
        return None

    file_content = ContentFile(json.dumps(geojson).encode("utf-8"))
    file_name = f"{vc_id}.geojson"
    path = geojson_upload_service.upload_file_get_path(
        str(vc_id), file_content, file_name=file_name
    )
    return path
