# Copyright © 2026 Technology Matters
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

"""Tests for the verify_geojson_s3 management command."""

import io
import json
from io import StringIO
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.management import call_command

from apps.shared_data.models import DataEntry, VisualizationConfig

pytestmark = pytest.mark.django_db

CONFIG = {
    "datasetConfig": {"longitude": "lng", "latitude": "lat"},
    "annotateConfig": {"dataPoints": [{"label": "Name", "column": "name"}]},
}
CSV_CONTENT = "name,lng,lat\nsite,-77.95,-1.65\n"
GENERATED_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-77.95, -1.65]},
            "properties": {"title": None, "fields": '[{"label": "Name", "value": "site"}]'},
        }
    ],
}

STORED_DIFFERENT_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
            "properties": {"title": None, "fields": "[]"},
        }
    ],
}


def bytes_io(text):
    return io.BytesIO(text.encode("utf-8"))


def set_config(visualization_config, geojson_s3_key=None):
    visualization_config.configuration = CONFIG
    visualization_config.geojson_s3_key = geojson_s3_key
    visualization_config.save()


def run_command(**options):
    out = StringIO()
    call_command("verify_geojson_s3", stdout=out, **options)
    return out.getvalue()


@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_matching_s3_object_reports_match(mock_source, mock_stored, visualization_config):
    """Stored S3 object identical to regenerated geojson -> MATCH."""
    set_config(visualization_config, geojson_s3_key="geojson/x/vc.geojson")
    mock_source.return_value = bytes_io(CSV_CONTENT)
    mock_stored.return_value = bytes_io(json.dumps(GENERATED_GEOJSON))

    output = run_command()

    assert "MATCH" in output
    assert "identical to S3" in output


@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_differing_s3_object_flagged_with_diff(mock_source, mock_stored, visualization_config):
    """Stored object that no longer matches generation -> DIFF with details."""
    set_config(visualization_config, geojson_s3_key="geojson/x/vc.geojson")
    mock_source.return_value = bytes_io(CSV_CONTENT)
    mock_stored.return_value = bytes_io(json.dumps(STORED_DIFFERENT_GEOJSON))

    output = run_command()

    assert "DIFF" in output
    assert "stored 1 vs generated 1 features" in output
    assert "first differing feature 0: geometry" in output


@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_no_s3_key_with_successful_generation_reports_generates(
    mock_source, mock_stored, visualization_config
):
    """Nothing on S3: the command reports whether generation succeeds."""
    set_config(visualization_config)
    mock_source.return_value = bytes_io(CSV_CONTENT)

    output = run_command()

    assert "GENERATES" in output
    assert "1 features" in output


@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_generation_returning_none_reports_no_geojson(
    mock_source, mock_stored, visualization_config
):
    """Unresolvable columns (prod 'latitude: ""' case) -> NO_GEOJSON."""
    visualization_config.configuration = {
        "datasetConfig": {"longitude": "lng", "latitude": ""},
        "annotateConfig": {"dataPoints": []},
    }
    visualization_config.save()
    mock_source.return_value = bytes_io(CSV_CONTENT)

    output = run_command()

    assert "NO_GEOJSON" in output


@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_stale_s3_key_when_generation_yields_nothing(
    mock_source, mock_stored, visualization_config
):
    """Key set on S3 but the pipeline no longer produces geojson -> STALE."""
    set_config(visualization_config, geojson_s3_key="geojson/x/vc.geojson")
    visualization_config.configuration = {
        "datasetConfig": {"longitude": "lng", "latitude": ""},
        "annotateConfig": {"dataPoints": []},
    }
    visualization_config.save()
    mock_source.return_value = bytes_io(CSV_CONTENT)

    output = run_command()

    assert "STALE" in output
    assert "generation yields nothing" in output


@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_generation_error_is_flagged_not_raised(mock_source, mock_stored, visualization_config):
    """A failing generation (e.g. missing source file) becomes GENERATION_ERROR."""
    set_config(visualization_config, geojson_s3_key=None)
    mock_source.side_effect = FileNotFoundError("File does not exist: x/test_data.csv")

    output = run_command()

    assert "GENERATION_ERROR" in output
    assert "FileNotFoundError" in output


@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_unreadable_s3_object_is_flagged(mock_source, mock_stored, visualization_config):
    """A missing/corrupt S3 object becomes UNREADABLE, not a crash."""
    set_config(visualization_config, geojson_s3_key="geojson/x/vc.geojson")
    mock_source.return_value = bytes_io(CSV_CONTENT)
    mock_stored.side_effect = FileNotFoundError("The specified key does not exist.")

    output = run_command()

    assert "UNREADABLE" in output


@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_out_of_scope_resource_types_are_skipped(mock_source, mock_stored, visualization_config):
    """Only dataset (csv/xls/xlsx) and KML/KMZ configs are checked."""
    set_config(visualization_config, geojson_s3_key=None)
    mock_source.return_value = bytes_io(CSV_CONTENT)
    # GPX is a GIS type but outside the command's scope: it must not appear.
    gpx_entry = DataEntry.objects.create(
        size=1,
        url=f"{settings.DATA_ENTRY_FILE_BASE_URL}/{visualization_config.created_by.id}/test_data.gpx",
        created_by=visualization_config.created_by,
        resource_type="gpx",
    )
    VisualizationConfig.objects.create(
        title="gpx viz",
        readable_id="zzzzzzzz",
        configuration=CONFIG,
        geojson_s3_key=None,
        data_entry=gpx_entry,
    )

    output = run_command()

    assert "gpx" not in output
    assert output.count("vc=") == 1
