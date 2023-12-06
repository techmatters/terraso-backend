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
from importlib import resources
from unittest.mock import patch

import pytest
import requests

from apps.core.gis.mapbox import get_line_delimited_geojson
from apps.shared_data.models import VisualizationConfig
from apps.shared_data.visualization_tileset_tasks import (
    create_mapbox_tileset,
    remove_mapbox_tileset,
)

from ..core.gis.test_parsers import KML_TEST_FILES

pytestmark = pytest.mark.django_db


def create_mock_response(response):
    mock_response = requests.Response()
    mock_response.status_code = response["status_code"]
    mock_response.json = lambda: response["json_data"]
    return mock_response


@patch("apps.shared_data.visualization_tileset_tasks.data_entry_upload_service.get_file")
@patch("apps.core.gis.mapbox.requests.post")
def test_create_mapbox_tileset_dataset_success(
    mock_request_post, mock_get_file, visualization_config
):
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

    assert json.loads(mock_request_post.call_args_list[0][1]["files"][0][1][1]) == {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-0.1805502450716432, -78.48306234911033]},
        "properties": {
            "title": None,
            "fields": '[{"label": "label", "value": "val3"}]',
        },
    }

    assert (
        mock_request_post.call_args_list[1][1]["json"]["name"]
        == f"development - {visualization_config.title}"[:64]
    )


@pytest.mark.parametrize(
    "kml_file_path_expected",
    KML_TEST_FILES,
)
@patch("apps.shared_data.services.data_entry_upload_service.get_file")
@patch("apps.core.gis.mapbox.requests.post")
def test_create_mapbox_tileset_gis_dataentry_success(
    mock_request_post, mock_get_file, visualization_config_kml, kml_file_path_expected
):
    kml_file_path = kml_file_path_expected[0]

    expected_file_path = kml_file_path_expected[1]
    with open(resources.files("tests").joinpath(expected_file_path), "rb") as file:
        expected_json = json.load(file)

    with open(resources.files("tests").joinpath(kml_file_path), "rb") as file:
        mock_get_file.return_value = file
        mock_responses = [
            {"status_code": 200, "json_data": {"id": "tileset-id-1"}},
            {"status_code": 200, "json_data": {}},
            {"status_code": 200, "json_data": {}},
        ]
        mock_request_post.side_effect = [
            create_mock_response(response) for response in mock_responses
        ]
        create_mapbox_tileset(visualization_config_kml.id)

    updated_visualization_config = VisualizationConfig.objects.get(id=visualization_config_kml.id)
    assert updated_visualization_config.mapbox_tileset_id is not None
    assert mock_request_post.call_count == 3

    assert mock_request_post.call_args_list[0][1]["files"][0][1][1] == get_line_delimited_geojson(
        expected_json
    )

    assert (
        mock_request_post.call_args_list[1][1]["json"]["name"]
        == f"development - {visualization_config_kml.title}"[:64]
    )


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
