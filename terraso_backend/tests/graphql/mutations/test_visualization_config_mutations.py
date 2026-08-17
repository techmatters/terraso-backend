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

from unittest import mock
from unittest.mock import patch

import pytest

from apps.shared_data.models import VisualizationConfig

pytestmark = pytest.mark.django_db


@mock.patch("apps.graphql.schema.visualization_config.upload_geojson_to_s3_precreate")
def test_visualization_config_add(
    mock_upload_precreate, client_query, groups, data_entries, data_entries_memberships
):
    mock_upload_precreate.return_value = "geojson/test-uuid/test-vc.geojson"
    group_id = str(groups[0].id)
    data_entry_id = str(data_entries[0].id)
    new_data = {
        "title": "Test title",
        "configuration": '{"key": "value"}',
        "ownerId": group_id,
        "ownerType": "group",
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
              dataEntry { id }
              owner {
                ... on GroupNode { id }
              }
            }
            errors
          }
        }
        """,
        variables={"input": new_data},
    )

    json_response = response.json()

    result = json_response["data"]["addVisualizationConfig"]["visualizationConfig"]

    assert result == {
        "slug": "test-title",
        "title": "Test title",
        "configuration": '{"key": "value"}',
        "owner": {"id": group_id},
        "dataEntry": {"id": data_entry_id},
    }
    mock_upload_precreate.assert_called_once()


@mock.patch("apps.graphql.schema.visualization_config.upload_geojson_to_s3_precreate")
def test_visualization_config_add_works_for_duplicated_title(
    mock_upload_precreate, client_query, visualization_configs, data_entries
):
    mock_upload_precreate.return_value = "geojson/test-uuid/test-vc.geojson"
    new_data = {
        "title": visualization_configs[0].title,
        "configuration": '{"key": "value"}',
        "ownerId": str(visualization_configs[0].owner.id),
        "ownerType": "group",
        "dataEntryId": str(data_entries[0].id),
    }

    response = client_query(
        """
        mutation addVisualizationConfig($input: VisualizationConfigAddMutationInput!) {
          addVisualizationConfig(input: $input) {
            visualizationConfig {
              title
              readableId
            }
            errors
          }
        }
        """,
        variables={"input": new_data},
    )
    response = response.json()

    result = response["data"]["addVisualizationConfig"]["visualizationConfig"]

    assert result["title"] == visualization_configs[0].title
    assert result["readableId"] is not None

    mock_upload_precreate.assert_called_once()


@mock.patch("apps.graphql.schema.visualization_config.upload_geojson_to_s3")
def test_visualization_config_update_by_creator_works(
    mock_upload_geojson, client_query, visualization_configs
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
    mock_upload_geojson.assert_called_once()


@mock.patch("apps.graphql.schema.visualization_config.upload_geojson_to_s3")
def test_visualization_config_update_by_non_creator_fails_due_permission_check(
    mock_upload_geojson, client_query, visualization_configs, users
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
    mock_upload_geojson.assert_not_called()


@patch("apps.graphql.schema.visualization_config.geojson_upload_service.delete_file")
def test_visualization_config_delete_by_creator_works(
    mock_delete_file, client_query, visualization_configs
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
    # Verify S3 cleanup was called
    if old_visualization_config.geojson_s3_key:
        mock_delete_file.assert_called_once_with(old_visualization_config.geojson_s3_key)
    else:
        mock_delete_file.assert_not_called()


def test_visualization_config_delete_by_non_creator_fails_due_permission_check(
    client_query, visualization_configs, users
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


@mock.patch("apps.graphql.schema.visualization_config.upload_geojson_to_s3_precreate")
def test_visualization_config_add_with_story_map_owner(
    mock_upload_precreate, client_query, story_maps, story_map_data_entry
):
    mock_upload_precreate.return_value = "geojson/test-uuid/test-vc.geojson"
    story_map = story_maps[0]
    story_map_id = str(story_map.id)
    data_entry_id = str(story_map_data_entry.id)
    new_data = {
        "title": "Test Story Map Viz",
        "configuration": '{"key": "value"}',
        "ownerId": story_map_id,
        "ownerType": "story_map",
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
              dataEntry { id }
              owner {
                ... on StoryMapNode {
                  id
                  title
                }
              }
            }
            errors
          }
        }
        """,
        variables={"input": new_data},
    )

    json_response = response.json()

    result = json_response["data"]["addVisualizationConfig"]["visualizationConfig"]

    assert result["slug"] == "test-story-map-viz"
    assert result["title"] == "Test Story Map Viz"
    assert result["configuration"] == '{"key": "value"}'
    assert result["owner"]["id"] == story_map_id
    assert result["owner"]["title"] == story_map.title
    assert result["dataEntry"]["id"] == str(story_map_data_entry.id)
    mock_upload_precreate.assert_called_once()


@mock.patch("apps.graphql.schema.visualization_config.upload_geojson_to_s3_precreate")
def test_visualization_config_add_fails_with_invalid_story_map(
    mock_upload_precreate, client_query, data_entries, users
):
    invalid_story_map_id = "00000000-0000-0000-0000-000000000000"
    data_entry_id = str(data_entries[0].id)
    new_data = {
        "title": "Test title",
        "configuration": '{"key": "value"}',
        "ownerId": invalid_story_map_id,
        "ownerType": "story_map",
        "dataEntryId": data_entry_id,
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
    assert response["data"]["addVisualizationConfig"]["visualizationConfig"] is None
    mock_upload_precreate.assert_not_called()


@patch("apps.graphql.schema.visualization_config.upload_geojson_to_s3_precreate")
def test_visualization_config_add_s3_failure_no_zombie(
    mock_upload_precreate, client_query, groups, data_entries, data_entries_memberships
):
    """When S3 upload fails, no VC row is created."""
    mock_upload_precreate.side_effect = Exception("S3 timeout")

    group_id = str(groups[0].id)
    data_entry_id = str(data_entries[0].id)
    new_data = {
        "title": "Test title",
        "configuration": '{"key": "value"}',
        "ownerId": group_id,
        "ownerType": "group",
        "dataEntryId": data_entry_id,
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

    json_response = response.json()
    # Should have errors and no VC data
    assert json_response["data"]["addVisualizationConfig"]["visualizationConfig"] is None
    assert json_response["data"]["addVisualizationConfig"]["errors"] is not None
    # No VC should exist in DB
    assert VisualizationConfig.objects.count() == 0
