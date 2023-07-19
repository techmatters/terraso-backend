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
from unittest import mock

import pytest

from apps.shared_data.models import VisualizationConfig

pytestmark = pytest.mark.django_db


@mock.patch("apps.graphql.schema.visualization_config.start_create_mapbox_tileset_task")
def test_visualization_config_add(
    mock_create_tileset, client_query, visualization_configs, data_entries
):
    group_id = str(visualization_configs[0].group.id)
    data_entry_id = str(data_entries[0].id)
    new_data = {
        "title": "Test title",
        "configuration": '{"key": "value"}',
        "groupId": group_id,
        "dataEntryId": data_entry_id,
    }

    response = client_query(
        """
        mutation addVisualizationConfig($input: VisualizationConfigAddMutationInput!) {
          addVisualizationConfig(input: $input) {
            visualizationConfig {
              slug
              title
              configuration
              group { id }
              dataEntry { id }
            }
          }
        }
        """,
        variables={"input": new_data},
    )

    result = response.json()["data"]["addVisualizationConfig"]["visualizationConfig"]

    assert result == {
        "slug": "test-title",
        "title": "Test title",
        "configuration": '{"key": "value"}',
        "group": {"id": group_id},
        "dataEntry": {"id": data_entry_id},
    }
    mock_create_tileset.assert_called_once()


@mock.patch("apps.graphql.schema.visualization_config.start_create_mapbox_tileset_task")
def test_visualization_config_add_fails_due_uniqueness_check(
    mock_create_tileset, client_query, visualization_configs, data_entries
):
    new_data = {
        "title": visualization_configs[0].title,
        "configuration": '{"key": "value"}',
        "groupId": str(visualization_configs[0].group.id),
        "dataEntryId": str(data_entries[0].id),
    }

    response = client_query(
        """
        mutation addVisualizationConfig($input: VisualizationConfigAddMutationInput!) {
          addVisualizationConfig(input: $input) {
            visualizationConfig {
              id
            }
            errors
          }
        }
        """,
        variables={"input": new_data},
    )
    response = response.json()

    assert "errors" in response["data"]["addVisualizationConfig"]
    error_message = json.loads(response["data"]["addVisualizationConfig"]["errors"][0]["message"])[
        0
    ]
    assert error_message["code"] == "unique"
    mock_create_tileset.assert_not_called()


@mock.patch("apps.graphql.schema.visualization_config.start_create_mapbox_tileset_task")
def test_visualization_config_update_by_creator_works(
    mock_create_tileset, client_query, visualization_configs
):
    old_visualization_config = visualization_configs[0]

    new_data = {
        "id": str(old_visualization_config.id),
        "configuration": '{"key": "value"}',
    }
    response = client_query(
        """
        mutation updateVisualizationConfig($input: VisualizationConfigUpdateMutationInput!) {
          updateVisualizationConfig(input: $input) {
            visualizationConfig {
              id
              configuration
            }
          }
        }
        """,
        variables={"input": new_data},
    )
    result = response.json()["data"]["updateVisualizationConfig"]["visualizationConfig"]

    assert result == new_data
    mock_create_tileset.assert_called_once()


@mock.patch("apps.graphql.schema.visualization_config.start_create_mapbox_tileset_task")
def test_visualization_config_update_by_non_creator_fails_due_permission_check(
    mock_create_tileset, client_query, visualization_configs, users
):
    old_visualization_config = visualization_configs[0]

    # Let's force old data creator be different from client query user
    old_visualization_config.created_by = users[2]
    old_visualization_config.save()

    new_data = {
        "id": str(old_visualization_config.id),
        "configuration": '{"key": "value"}',
    }

    response = client_query(
        """
        mutation updateVisualizationConfig($input: VisualizationConfigUpdateMutationInput!) {
          updateVisualizationConfig(input: $input) {
            visualizationConfig {
              id
            }
            errors
          }
        }
        """,
        variables={"input": new_data},
    )
    response = response.json()

    assert "errors" in response["data"]["updateVisualizationConfig"]
    assert (
        "update_not_allowed"
        in response["data"]["updateVisualizationConfig"]["errors"][0]["message"]
    )
    mock_create_tileset.assert_not_called()


@mock.patch("apps.graphql.schema.visualization_config.start_remove_mapbox_tileset_task")
def test_visualization_config_delete_by_creator_works(
    mock_remove_tileset, client_query, visualization_configs
):
    old_visualization_config = visualization_configs[0]

    response = client_query(
        """
        mutation deleteVisualizationConfig($input: VisualizationConfigDeleteMutationInput!){
          deleteVisualizationConfig(input: $input) {
            visualizationConfig {
              configuration
            }
          }
        }

        """,
        variables={"input": {"id": str(old_visualization_config.id)}},
    )

    visualization_config_result = response.json()["data"]["deleteVisualizationConfig"][
        "visualizationConfig"
    ]

    assert visualization_config_result["configuration"] == old_visualization_config.configuration
    assert not VisualizationConfig.objects.filter(id=old_visualization_config.id)
    mock_remove_tileset.assert_called_once()


@mock.patch("apps.graphql.schema.visualization_config.start_remove_mapbox_tileset_task")
def test_visualization_config_delete_by_non_creator_fails_due_permission_check(
    mock_remove_tileset, client_query, visualization_configs, users
):
    old_visualization_config = visualization_configs[0]

    # Let's force old data creator be different from client query user
    old_visualization_config.created_by = users[2]
    old_visualization_config.save()

    response = client_query(
        """
        mutation deleteVisualizationConfig($input: VisualizationConfigDeleteMutationInput!){
          deleteVisualizationConfig(input: $input) {
            visualizationConfig {
              configuration
            }
            errors
          }
        }

        """,
        variables={"input": {"id": str(old_visualization_config.id)}},
    )

    response = response.json()

    assert "errors" in response["data"]["deleteVisualizationConfig"]
    assert (
        "delete_not_allowed"
        in response["data"]["deleteVisualizationConfig"]["errors"][0]["message"]
    )
    mock_remove_tileset.assert_not_called()
