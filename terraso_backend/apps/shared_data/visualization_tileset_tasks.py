import csv
import json
import threading

import pandas
import structlog
from django.conf import settings

from apps.core.gis.mapbox import create_tileset, remove_tileset
from apps.shared_data.services import data_entry_upload_service

from .models import VisualizationConfig

logger = structlog.get_logger(__name__)


class AsyncTaskHandler:
    def start_task(self, method, args):
        t = threading.Thread(target=method, args=[*args], daemon=True)
        t.start()


def start_create_mapbox_tileset_task(visualization_id):
    AsyncTaskHandler().start_task(create_mapbox_tileset, [visualization_id])


def start_remove_mapbox_tileset_task(tileset_id):
    AsyncTaskHandler().start_task(remove_mapbox_tileset, [tileset_id])


def get_rows_from_file(data_entry):
    type = data_entry.resource_type
    if type.startswith("csv"):
        file = data_entry_upload_service.get_file(data_entry.s3_object_name, "rt")
        reader = csv.reader(file)
        return [row for row in reader]
    elif type.startswith("xls"):
        file = data_entry_upload_service.get_file(data_entry.s3_object_name, "rb")
        df = pandas.read_excel(file)
        rows = df.values.tolist()
        return [df.columns.tolist()] + rows
    else:
        raise Exception(
            "Invalid file type for creating mapbox tileset",
            extra={"file_type": type, "data_entry_id": data_entry.id},
        )


def remove_mapbox_tileset(tileset_id):
    if tileset_id is None:
        return
    try:
        remove_tileset(tileset_id)
    except Exception as error:
        logger.exception(
            "Error deleting mapbox tileset",
            extra={"tileset_id": tileset_id, "error": str(error)},
        )


def create_mapbox_tileset(visualization_id):
    logger.info("Creating mapbox tileset", visualization_id=visualization_id)
    visualization = VisualizationConfig.objects.get(pk=visualization_id)
    data_entry = visualization.data_entry
    group_entry = visualization.group

    # Delete mapbox tileset if needed
    remove_mapbox_tileset(visualization.mapbox_tileset_id)

    try:
        rows = get_rows_from_file(data_entry)

        first_row = rows[0]

        dataset_config = visualization.configuration["datasetConfig"]
        annotate_config = visualization.configuration["annotateConfig"]

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

        geojson = {
            "type": "FeatureCollection",
            "features": features,
        }
        logger.info(
            "Geojson generated for mapbox tileset",
            visualization_id=visualization_id,
            rows=len(rows),
        )
        title = f"{settings.ENV} - {visualization.title}"[:64]
        description = f"{settings.ENV} - {group_entry.name} - {visualization.title}"
        id = str(visualization.id).replace("-", "")
        tileset_id = create_tileset(id, geojson, title, description)
        logger.info(
            "Mapbox tileset created",
            visualization_id=visualization_id,
            tileset_id=tileset_id,
        )
        visualization.mapbox_tileset_id = tileset_id
        visualization.save()
        logger.info(
            "Mapbox tileset id saved",
            visualization_id=visualization_id,
            tileset_id=tileset_id,
        )
    except Exception as error:
        logger.exception(
            "Error creating mapbox tileset",
            extra={"data_entry_id": visualization.data_entry.id, "error": str(error)},
        )
