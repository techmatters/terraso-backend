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


def test_users_query(client_query, users):
    response = client_query(
        """
        {users {
          edges {
            node {
              email
              profileImage
            }
          }
        }}
        """
    )
    edges = response.json()["data"]["users"]["edges"]
    users_result_nodes = [edge["node"] for edge in edges]
    for user in users:
        user_node = next(item for item in users_result_nodes if item["email"] == user.email)
        assert user_node
        assert user.profile_image == user_node["profileImage"]


def test_user_get_one_by_id(client_query, users):
    user = users[0]
    query = (
        """
        {user(id: "%s") {
          id
          email
          profileImage
        }}
        """
        % user.id
    )
    response = client_query(query)
    user_result = response.json()["data"]["user"]
    assert user_result["id"] == str(user.id)
    assert user_result["email"] == user.email
    assert user_result["profileImage"] == user.profile_image


def test_users_query_has_total_count(client_query, users):
    response = client_query(
        """
        {users {
          totalCount
          edges {
            node {
              email
            }
          }
        }}
        """
    )
    total_count = response.json()["data"]["users"]["totalCount"]

    assert total_count == len(users)
