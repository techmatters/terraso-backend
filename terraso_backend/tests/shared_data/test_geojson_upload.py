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

import io
import json
from unittest.mock import patch

import pytest

from apps.shared_data.geojson_upload import upload_geojson_to_s3
from apps.shared_data.models import VisualizationConfig

pytestmark = pytest.mark.django_db


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.geojson_upload_service.upload_file_get_path")
def test_upload_geojson_to_s3_dataset_success(
    mock_upload_path, mock_get_file, visualization_config
):
    """Dataset CSV upload generates correct GeoJSON and stores the S3 key."""
    visualization_config.configuration = {
        "datasetConfig": {
            "longitude": "lng",
            "latitude": "lat",
        },
        "annotateConfig": {
            "dataPoints": [
                {
                    "label": "label",
                    "column": "col1",
                }
            ]
        },
    }
    visualization_config.save()
    mock_get_file.return_value = io.StringIO(
        "lat,lng,col1\n-78.48306234911033,-0.1805502450716432,val3"
    )
    mock_upload_path.return_value = "geojson/test-id/test-vc-id.geojson"

    result = upload_geojson_to_s3(visualization_config.id)

    updated_vc = VisualizationConfig.objects.get(id=visualization_config.id)
    assert updated_vc.geojson_s3_key == "geojson/test-id/test-vc-id.geojson"
    assert result == "geojson/test-id/test-vc-id.geojson"
    mock_upload_path.assert_called_once()

    # Verify the GeoJSON content that was uploaded
    call_args = mock_upload_path.call_args
    pos_args, kwargs = call_args
    uploaded_file = kwargs.get("file", pos_args[1])
    uploaded_content = json.loads(uploaded_file.read().decode("utf-8"))
    assert uploaded_content["type"] == "FeatureCollection"
    assert len(uploaded_content["features"]) == 1
    assert uploaded_content["features"][0]["geometry"]["coordinates"] == [
        -0.1805502450716432,
        -78.48306234911033,
    ]


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_upload_geojson_to_s3_no_geojson(mock_get_file, visualization_config):
    """When resource type is not spreadsheet or GIS, returns None without crashing."""
    visualization_config.data_entry.resource_type = "pdf"
    visualization_config.data_entry.save()

    result = upload_geojson_to_s3(visualization_config.id)

    assert result is None
    updated_vc = VisualizationConfig.objects.get(id=visualization_config.id)
    assert updated_vc.geojson_s3_key is None


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.geojson_upload_service.upload_file_get_path")
def test_upload_geojson_to_s3_cleans_up_old_key(
    mock_upload_path, mock_get_file, visualization_config
):
    """When VC already has a geojson_s3_key, the old key's file is deleted."""
    visualization_config.configuration = {
        "datasetConfig": {
            "longitude": "lng",
            "latitude": "lat",
        },
        "annotateConfig": {
            "dataPoints": [
                {
                    "label": "label",
                    "column": "col1",
                }
            ]
        },
    }
    visualization_config.geojson_s3_key = "geojson/old-id/old-file.geojson"
    visualization_config.save()
    mock_get_file.return_value = io.StringIO(
        "lat,lng,col1\n-78.48306234911033,-0.1805502450716432,val3"
    )
    mock_upload_path.return_value = "geojson/new-id/new-file.geojson"

    with patch("apps.shared_data.geojson_upload.geojson_upload_service.delete_file") as mock_delete:
        result = upload_geojson_to_s3(visualization_config.id)

    mock_delete.assert_called_once_with("geojson/old-id/old-file.geojson")
    updated_vc = VisualizationConfig.objects.get(id=visualization_config.id)
    assert updated_vc.geojson_s3_key == "geojson/new-id/new-file.geojson"
    assert result == "geojson/new-id/new-file.geojson"


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.geojson_upload_service.upload_file_get_path")
def test_upload_geojson_to_s3_precreate_dataset_success(
    mock_upload_path, mock_get_file, visualization_config
):
    """upload_geojson_to_s3_precreate uploads GeoJSON and returns S3 key."""
    from apps.shared_data.geojson_upload import upload_geojson_to_s3_precreate

    vc = visualization_config
    vc.configuration = {
        "datasetConfig": {
            "longitude": "lng",
            "latitude": "lat",
        },
        "annotateConfig": {
            "dataPoints": [
                {
                    "label": "label",
                    "column": "col1",
                }
            ]
        },
    }
    vc.save()

    mock_get_file.return_value = io.StringIO(
        "lat,lng,col1\n-78.48306234911033,-0.1805502450716432,val3"
    )
    mock_upload_path.return_value = "geojson/test-uuid/test-uuid.geojson"

    result = upload_geojson_to_s3_precreate(
        "test-uuid", vc.data_entry, json.dumps(vc.configuration)
    )

    assert result == "geojson/test-uuid/test-uuid.geojson"
