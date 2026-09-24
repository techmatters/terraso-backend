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
import io
import json
import math
import re
import unicodedata

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


def _sniff_delimiter(text):
    """Return the delimiter character for `text`, restricted to comma/semicolon/tab.

    Falls back to semicolon when sniffing fails but a semicolon is present in
    the first line (e.g. quoted semicolon exports the Sniffer cannot decide
    on). Returns comma when nothing else applies.
    """
    try:
        return csv.Sniffer().sniff(text, delimiters=",;\t").delimiter
    except csv.Error:
        if ";" in text.splitlines()[0]:
            return ";"
        return ","


def get_rows_from_file(data_entry):
    type = data_entry.resource_type
    if type.startswith("csv"):
        # Read in binary mode and decode as UTF-8 with BOM stripping: files
        # exported from spreadsheets often start with a UTF-8 BOM, and plain
        # text-mode reading leaves "\ufeff" glued to the first header.
        file = data_entry_upload_service.get_file(data_entry.s3_object_name, "rb")
        with io.TextIOWrapper(file, encoding="utf-8-sig", newline="") as text:
            first_line = text.readline()
            body = first_line + text.read()
        rows = [row for row in csv.reader(io.StringIO(body))]
        if rows and len(rows[0]) == 1 and (";" in first_line or "\t" in first_line):
            # Delimiter fallback: the header row collapsing to a single column
            # means the default comma dialect mangled the file; re-parse with
            # a sniffed delimiter (semicolon/tab exports, e.g. "start";"end";...).
            delimiter = _sniff_delimiter(body)
            if delimiter != ",":
                rows = [row for row in csv.reader(io.StringIO(body), delimiter=delimiter)]
        return rows
    elif type.startswith("xls"):
        file = data_entry_upload_service.get_file(data_entry.s3_object_name, "rb")
        df = pandas.read_excel(file, dtype=str)
        rows = df.values.tolist()
        return [df.columns.tolist()] + rows
    else:
        raise Exception(  # noqa: TRY002
            "Invalid file type for processing data entry",
            extra={"file_type": type, "data_entry_id": data_entry.id},
        )


def get_owner_name(visualization):
    if isinstance(visualization.owner, (Landscape, Group)):
        return visualization.owner.name
    elif isinstance(visualization.owner, StoryMap):
        return visualization.owner.title
    return "Unknown"


def _normalize_column_name(value):
    """strip + remove a leading BOM + NFKC normalization + casefold."""
    return unicodedata.normalize("NFKC", value.strip().lstrip("\ufeff")).casefold()


def _mojibake_repair(value):
    """Repair double-encoded UTF-8 ('mojibake') text when it round-trips.

    e.g. 'TÃ©cnico ' (UTF-8 read as latin-1) -> 'Técnico '. Returns the
    original value when the round-trip is not possible.

    If we're still getting issues later, this is the sledgehammer for this
    problem: https://ftfy.readthedocs.io/en/latest/
    """
    try:
        return value.encode("latin-1").decode("utf-8")
    except UnicodeError:
        return value


def _resolve_column_index(header, column):
    if column is None:
        return None

    # Tier 1: exact
    for index, head in enumerate(header):
        if head == column:
            return index

    # Tier 2: stripped on both sides
    stripped = column.strip()
    for index, head in enumerate(header):
        if head.strip() == stripped:
            return index

    # Tier 3: normalized on both sides
    normalized = _normalize_column_name(column)
    for index, head in enumerate(header):
        if _normalize_column_name(head) == normalized:
            return index

    # Tier 4: repair mojibake on both sides, then retry the ladder above
    # (won't loop infinitely because _mojibake_repair is idempotent).
    repaired = _mojibake_repair(column)
    if repaired != column:
        return _resolve_column_index([_mojibake_repair(head) for head in header], repaired)

    return None


def _parse_coordinate(value):
    """Parse a coordinate, tolerating comma decimals ('-77,9522722').

    Returns None when the value cannot be parsed as a float. NaN/inf values
    (e.g. blank cells read by the xls branch) are not coordinates.
    """
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = None
    if result is not None and not math.isfinite(result):
        return None
    if result is not None:
        return result
    if isinstance(value, str) and re.fullmatch(r"[-+]?\d+(,\d+)?", value.strip()):
        try:
            return float(value.strip().replace(",", "."))
        except ValueError:
            return None
    return None


def _get_geojson_from_dataset(data_entry, configuration):
    rows = get_rows_from_file(data_entry)

    if not rows:
        logger.warning(
            "Cannot generate geojson: data entry file has no rows",
            extra={"data_entry_id": data_entry.id},
        )
        return None

    first_row = rows[0]

    dataset_config = configuration["datasetConfig"]
    annotate_config = configuration["annotateConfig"]

    longitude_index = _resolve_column_index(first_row, dataset_config.get("longitude"))
    latitude_index = _resolve_column_index(first_row, dataset_config.get("latitude"))
    if longitude_index is None or latitude_index is None:
        logger.warning(
            "Cannot generate geojson: longitude/latitude columns not found in data entry",
            extra={
                "data_entry_id": data_entry.id,
                "longitude": dataset_config.get("longitude"),
                "latitude": dataset_config.get("latitude"),
            },
        )
        return None

    data_points_indexes = []
    for data_point in annotate_config["dataPoints"]:
        index = _resolve_column_index(first_row, data_point["column"])
        if index is None:
            logger.warning(
                "Skipping data point: column not found in data entry",
                extra={"data_entry_id": data_entry.id, "column": data_point["column"]},
            )
            continue
        data_points_indexes.append(
            {
                "label": data_point.get("label", data_point["column"]),
                "index": index,
            }
        )

    annotation_title = annotate_config.get("annotationTitle")

    title_index = _resolve_column_index(first_row, annotation_title) if annotation_title else None

    max_index = max(
        index
        for index in [longitude_index, latitude_index, title_index]
        + [data_point["index"] for data_point in data_points_indexes]
        if index is not None
    )

    features = []
    skipped_ragged = 0
    skipped_unparseable = 0
    # rows[0] is the header row: not a data point, and its cells are column
    # names, not coordinates — exclude it from feature generation (and from
    # the skip counts below).
    for row in rows[1:]:
        if len(row) <= max_index:
            # Ragged row shorter than the configured columns: skip it
            # instead of crashing on an out-of-range index.
            skipped_ragged += 1
            continue

        fields = [
            {
                "label": data_point["label"],
                "value": row[data_point["index"]],
            }
            for data_point in data_points_indexes
        ]

        properties = {
            "title": row[title_index] if title_index is not None else None,
            "fields": json.dumps(fields),
        }

        longitude = _parse_coordinate(row[longitude_index])
        latitude = _parse_coordinate(row[latitude_index])
        if longitude is None or latitude is None:
            skipped_unparseable += 1
            continue

        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [longitude, latitude],
                },
                "properties": properties,
            }
        )

    if skipped_ragged or skipped_unparseable:
        logger.warning(
            "Skipped rows without usable coordinates while generating geojson",
            extra={
                "data_entry_id": data_entry.id,
                "skipped_ragged": skipped_ragged,
                "skipped_unparseable": skipped_unparseable,
            },
        )

    if not features:
        logger.warning(
            "Cannot generate geojson: no rows with parseable coordinates",
            extra={"data_entry_id": data_entry.id},
        )
        return None

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def _get_geojson_from_gis(data_entry):
    file = data_entry_upload_service.get_file(data_entry.s3_object_name, "rb")
    return parse_file_to_geojson(file)


def get_geojson_from_data_entry(data_entry, visualization):
    is_dataset = (
        f".{data_entry.resource_type}" in settings.DATA_ENTRY_SPREADSHEET_TYPES.keys()  # noqa: SIM118
    )
    is_gis = f".{data_entry.resource_type}" in settings.DATA_ENTRY_GIS_TYPES.keys()  # noqa: SIM118

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
    except ValueError as e:
        logger.warning(
            "Skipping S3 upload: cannot generate geojson from this data entry",
            extra={
                "visualization_id": visualization_id,
                "resource_type": data_entry.resource_type,
                "reason": str(e),
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
        except Exception as e:  # noqa: BLE001
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

    is_dataset = (
        f".{data_entry.resource_type}" in settings.DATA_ENTRY_SPREADSHEET_TYPES.keys()  # noqa: SIM118
    )
    is_gis = f".{data_entry.resource_type}" in settings.DATA_ENTRY_GIS_TYPES.keys()  # noqa: SIM118

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
        raise ValueError(
            "GeoJSON generation returned no data for this data entry; "
            "the visualization would have no spatial data to render."
        )

    file_content = ContentFile(json.dumps(geojson).encode("utf-8"))
    file_name = f"{vc_id}.geojson"
    path = geojson_upload_service.upload_file_get_path(
        str(vc_id), file_content, file_name=file_name
    )
    return path
