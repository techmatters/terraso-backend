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
from unittest.mock import patch

import pytest
import requests

from apps.shared_data.models import VisualizationConfig
from apps.shared_data.visualization_tileset_tasks import (
    create_mapbox_tileset,
    remove_mapbox_tileset,
)

pytestmark = pytest.mark.django_db


def create_mock_response(response):
    mock_response = requests.Response()
    mock_response.status_code = response["status_code"]
    mock_response.json = lambda: response["json_data"]
    return mock_response


@patch("apps.shared_data.visualization_tileset_tasks.data_entry_upload_service.get_file")
@patch("apps.core.gis.mapbox.requests.post")
def test_create_mapbox_tileset_success(mock_request_post, mock_get_file, visualization_config):
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
    mock_get_file.return_value = io.StringIO("lat,lng,col1\nval1,val2,val3")
    mock_responses = [
        {"status_code": 200, "json_data": {"id": "tileset-id-1"}},
        {"status_code": 200, "json_data": {}},
        {"status_code": 200, "json_data": {}},
    ]
    mock_request_post.side_effect = [create_mock_response(response) for response in mock_responses]
    create_mapbox_tileset(visualization_config.id)
    updated_visualization_config = VisualizationConfig.objects.get(id=visualization_config.id)
    assert updated_visualization_config.mapbox_tileset_id is not None
    assert mock_request_post.call_count == 3


@patch("apps.shared_data.visualization_tileset_tasks.data_entry_upload_service.get_file")
@patch("apps.core.gis.mapbox.requests.post")
def test_create_mapbox_tileset_fail(mock_request_post, mock_get_file, visualization_config):
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
    mock_get_file.return_value = io.StringIO("lat,lng,col1\nval1,val2,val3")
    mock_responses = [
        {"status_code": 400, "json_data": {}},
    ]
    mock_request_post.side_effect = [create_mock_response(response) for response in mock_responses]
    create_mapbox_tileset(visualization_config.id)
    updated_visualization_config = VisualizationConfig.objects.get(id=visualization_config.id)
    assert updated_visualization_config.mapbox_tileset_id is None
    assert mock_request_post.call_count == 1


@patch("apps.core.gis.mapbox.requests.delete")
def test_remove_mapbox_tileset_success(mock_request_delete):
    mock_responses = [
        {"status_code": 200},
        {"status_code": 204},
    ]
    mock_request_delete.side_effect = [
        create_mock_response(response) for response in mock_responses
    ]
    remove_mapbox_tileset("tileset-id-1")
    assert mock_request_delete.call_count == 2


@patch("apps.core.gis.mapbox.requests.delete")
def test_remove_mapbox_tileset_fail(mock_request_delete):
    mock_responses = [
        {"status_code": 500},
    ]
    mock_request_delete.side_effect = [
        create_mock_response(response) for response in mock_responses
    ]
    remove_mapbox_tileset("tileset-id-1")
    assert mock_request_delete.call_count == 1
