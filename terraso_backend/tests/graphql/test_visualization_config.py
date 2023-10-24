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

import pytest

pytestmark = pytest.mark.django_db


def test_visualization_configs_query(client_query, visualization_configs):
    response = client_query(
        """
        {visualizationConfigs {
          edges {
            node {
              configuration
            }
          }
        }}
        """
    )
    json_response = response.json()
    edges = json_response["data"]["visualizationConfigs"]["edges"]
    entries_result = [edge["node"]["configuration"] for edge in edges]

    for visualization_config in visualization_configs:
        assert visualization_config.configuration in entries_result


def test_visualization_config_get_one_by_id(client_query, visualization_configs):
    visualization_config = visualization_configs[0]
    query = (
        """
        {visualizationConfig(id: "%s") {
          id
          configuration
        }}
        """
        % visualization_config.id
    )
    response = client_query(query)
    visualization_config_result = response.json()["data"]["visualizationConfig"]

    assert visualization_config_result["id"] == str(visualization_config.id)
    assert visualization_config_result["configuration"] == visualization_config.configuration


def test_visualization_configs_query_has_total_count(client_query, visualization_configs):
    response = client_query(
        """
        {visualizationConfigs {
          totalCount
          edges {
            node {
              configuration
            }
          }
        }}
        """
    )
    total_count = response.json()["data"]["visualizationConfigs"]["totalCount"]

    assert total_count == len(visualization_configs)


def test_visualization_configs_filter_by_group_slug_filters_successfuly(
    client_query, visualization_configs, groups
):
    visualization_config_a = visualization_configs[0]
    visualization_config_b = visualization_configs[1]

    visualization_config_a.data_entry.shared_resources.create(target=groups[-1])
    visualization_config_b.data_entry.shared_resources.create(target=groups[-1])

    group_filter = groups[-1]

    response = client_query(
        """
        {visualizationConfigs(
          dataEntry_SharedResources_Target_Slug: "%s",
          dataEntry_SharedResources_TargetContentType: "%s"
        ) {
          edges {
            node {
              id
              dataEntry {
                sharedResources {
                  edges {
                    node {
                      target {
                        ... on GroupNode {
                          slug
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }}
        """
        % (group_filter.slug, "group")
    )
    json_response = response.json()
    edges = json_response["data"]["visualizationConfigs"]["edges"]
    visualization_configs_result = [edge["node"]["id"] for edge in edges]

    assert (
        edges[0]["node"]["dataEntry"]["sharedResources"]["edges"][1]["node"]["target"]["slug"]
        == group_filter.slug
    )

    assert len(visualization_configs_result) == 2
    assert str(visualization_config_a.id) in visualization_configs_result
    assert str(visualization_config_b.id) in visualization_configs_result


def test_visualization_configs_filter_by_group_id_filters_successfuly(
    client_query, visualization_configs, groups
):
    visualization_config_a = visualization_configs[0]
    visualization_config_b = visualization_configs[1]

    visualization_config_a.data_entry.shared_resources.create(target=groups[-1])
    visualization_config_b.data_entry.shared_resources.create(target=groups[-1])

    group_filter = groups[-1]

    response = client_query(
        """
        {visualizationConfigs(dataEntry_SharedResources_TargetObjectId: "%s") {
          edges {
            node {
              id
            }
          }
        }}
        """
        % group_filter.id
    )

    edges = response.json()["data"]["visualizationConfigs"]["edges"]
    visualization_configs_result = [edge["node"]["id"] for edge in edges]

    assert len(visualization_configs_result) == 2
    assert str(visualization_config_a.id) in visualization_configs_result
    assert str(visualization_config_b.id) in visualization_configs_result


def test_visualization_configs_returns_only_for_users_groups(
    client_query, visualization_config_current_user
):
    # It's being done a request for all configurations, but only the configurations
    # from logged user's group is expected to return.
    response = client_query(
        """
        {visualizationConfigs {
          edges {
            node {
              id
            }
          }
        }}
        """
    )

    edges = response.json()["data"]["visualizationConfigs"]["edges"]
    entries_result = [edge["node"]["id"] for edge in edges]

    assert len(entries_result) == 1
    assert entries_result[0] == str(visualization_config_current_user.id)
