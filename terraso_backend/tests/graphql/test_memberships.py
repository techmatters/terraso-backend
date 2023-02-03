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


def test_memberships_query(client_query, memberships):
    response = client_query(
        """
        {memberships {
          edges {
            node {
              group {
                slug
              }
              user {
                email
              }
              userRole
            }
          }
        }}
        """
    )
    edges = response.json()["data"]["memberships"]["edges"]
    nodes = [edge["node"] for edge in edges]

    memberships_email_returned = [
        (memb["group"]["slug"], memb["user"]["email"]) for memb in nodes
    ].sort()

    memberships_email_expected = [(memb.group.slug, memb.user.email) for memb in memberships].sort()

    assert memberships_email_returned == memberships_email_expected


def test_membership_get_one_by_id(client_query, memberships):
    membership = memberships[0]
    query = (
        """
        {membership(id: "%s") {
          id
        }}
        """
        % membership.id
    )
    response = client_query(query)
    membership_result = response.json()["data"]["membership"]

    assert membership_result["id"] == str(membership.id)


def test_memberships_query_has_total_count(client_query, memberships):
    response = client_query(
        """
        {memberships {
          totalCount
          edges {
            node {
              id
            }
          }
        }}
        """
    )
    total_count = response.json()["data"]["memberships"]["totalCount"]

    assert total_count == len(memberships)
