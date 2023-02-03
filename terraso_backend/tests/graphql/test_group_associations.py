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


def test_group_associations_query(client_query, group_associations):
    response = client_query(
        """
        {groupAssociations {
          edges {
            node {
              parentGroup {
                slug
              }
              childGroup {
                slug
              }
            }
          }
        }}
        """
    )
    edges = response.json()["data"]["groupAssociations"]["edges"]
    nodes = [edge["node"] for edge in edges]

    associations_returned = [
        (assoc["parentGroup"]["slug"], assoc["childGroup"]["slug"]) for assoc in nodes
    ]

    associations_expected = [
        (assoc.parent_group.slug, assoc.child_group.slug) for assoc in group_associations
    ]

    assert associations_expected == associations_returned


def test_group_association_get_one_by_id(client_query, group_associations):
    group_association = group_associations[0]
    query = (
        """
        {groupAssociation(id: "%s") {
          id
        }}
        """
        % group_association.id
    )
    response = client_query(query)

    group_association_result = response.json()["data"]["groupAssociation"]

    assert group_association_result["id"] == str(group_association.id)


def test_group_associations_query_has_total_count(client_query, group_associations):
    response = client_query(
        """
        {groupAssociations {
          totalCount
          edges {
            node {
              id
            }
          }
        }}
        """
    )
    total_count = response.json()["data"]["groupAssociations"]["totalCount"]

    assert total_count == len(group_associations)
