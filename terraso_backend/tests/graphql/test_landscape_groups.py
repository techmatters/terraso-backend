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


def test_landscape_groups_query(client_query, landscape_groups):
    response = client_query(
        """
        {landscapeGroups {
          edges {
            node {
              landscape {
                slug
              }
              group {
                slug
              }
              isDefaultLandscapeGroup
            }
          }
        }}
        """
    )
    edges = response.json()["data"]["landscapeGroups"]["edges"]
    nodes = [edge["node"] for edge in edges]

    landscapes_and_groups_returned = [
        (lsg["landscape"]["slug"], lsg["group"]["slug"]) for lsg in nodes
    ]

    landscapes_and_groups_expected = [
        (lsg.landscape.slug, lsg.group.slug) for lsg in landscape_groups
    ]

    assert landscapes_and_groups_expected == landscapes_and_groups_returned


def test_landscape_group_get_one_by_id(client_query, landscape_groups):
    landscape_group = landscape_groups[0]
    query = (
        """
        {landscapeGroup(id: "%s") {
          id
        }}
        """
        % landscape_group.id
    )
    response = client_query(query)

    landscape_group_response = response.json()["data"]["landscapeGroup"]

    assert landscape_group_response["id"] == str(landscape_group.id)


def test_landscape_groups_query_has_total_count(client_query, landscape_groups):
    response = client_query(
        """
        {landscapeGroups {
          totalCount
          edges {
            node {
              id
            }
          }
        }}
        """
    )
    total_count = response.json()["data"]["landscapeGroups"]["totalCount"]

    assert total_count == len(landscape_groups)
