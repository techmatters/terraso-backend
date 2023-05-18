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


def test_groups_query(client_query, groups):
    response = client_query(
        """
        {groups {
          edges {
            node {
              slug
            }
          }
        }}
        """
    )
    edges = response.json()["data"]["groups"]["edges"]
    groups_result = [edge["node"]["slug"] for edge in edges]

    for group in groups:
        assert group.slug in groups_result


def test_group_get_by_one_by_id(client_query, groups):
    group = groups[0]
    query = (
        """
        {group(id: "%s") {
          id
          slug
        }}
        """
        % group.id
    )
    response = client_query(query)
    group_result = response.json()["data"]["group"]

    assert group_result["id"] == str(group.id)
    assert group_result["slug"] == group.slug


def test_groups_query_has_total_count(client_query, groups):
    response = client_query(
        """
        {groups {
          totalCount
          edges {
            node {
              slug
            }
          }
        }}
        """
    )
    total_count = response.json()["data"]["groups"]["totalCount"]

    assert total_count == len(groups)


def test_project_groups_not_included_in_query(client_query, project):
    reponse = client_query(
        """
        {groups {
          totalCount
          edges {
            node {
              slug
              }
            }
          }
        }
        """
    )
    total_count = reponse.json()["data"]["groups"]["totalCount"]
    assert total_count == 0
