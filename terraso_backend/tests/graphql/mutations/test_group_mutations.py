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

import pytest

from apps.core.models import Group

pytestmark = pytest.mark.django_db


def test_groups_add(client_query):
    group_name = "Testing Group"
    response = client_query(
        """
        mutation addGroup($input: GroupAddMutationInput!){
          addGroup(input: $input) {
            group {
              id
              name
              membershipList {
                membershipType
              }
            }
          }
        }
        """,
        variables={"input": {"name": group_name}},
    )
    json_response = response.json()
    group_result = json_response["data"]["addGroup"]["group"]

    assert group_result["id"]
    assert group_result["membershipList"]["membershipType"] == "OPEN"
    assert group_result["name"] == group_name


def test_groups_add_closed(client_query):
    group_name = "Testing Group"
    response = client_query(
        """
        mutation addGroup($input: GroupAddMutationInput!){
          addGroup(input: $input) {
            group {
              id
              name
              membershipList {
                membershipType
              }
            }
          }
        }
        """,
        variables={"input": {"name": group_name, "membershipType": "CLOSED"}},
    )
    json_response = response.json()
    group_result = json_response["data"]["addGroup"]["group"]

    assert group_result["id"]
    assert group_result["membershipList"]["membershipType"] == "CLOSED"
    assert group_result["name"] == group_name


def test_groups_add_blocked_for_anonymous_user(client_query_no_token):
    group_name = "Testing Group"
    response = client_query_no_token(
        """
        mutation addGroup($input: GroupAddMutationInput!){
          addGroup(input: $input) {
            group {
              id
              name
            }
            errors
          }
        }
        """,
        variables={"input": {"name": group_name}},
    )

    error_result = response.json()["data"]["addGroup"]["errors"][0]

    assert error_result
    error_message = json.loads(error_result["message"])[0]
    assert error_message["code"] == "unauthorized"


def test_groups_add_has_created_by_filled_out(client_query, users):
    group_name = "Testing Group"
    group_creator = users[0]

    response = client_query(
        """
        mutation addGroup($input: GroupAddMutationInput!){
          addGroup(input: $input) {
            group {
              id
              name
              createdBy { email }
            }
          }
        }
        """,
        variables={"input": {"name": group_name}},
    )
    group_result = response.json()["data"]["addGroup"]["group"]

    assert group_result["id"]
    assert group_result["name"] == group_name
    assert group_result["createdBy"]["email"] == group_creator.email


def test_groups_add_duplicated(client_query, groups):
    group_name = groups[0].name
    response = client_query(
        """
        mutation addGroup($input: GroupAddMutationInput!){
          addGroup(input: $input) {
            group {
              id
              name
            }
            errors
          }
        }
        """,
        variables={"input": {"name": group_name}},
    )
    error_result = response.json()["data"]["addGroup"]["errors"][0]

    assert error_result
    error_message = json.loads(error_result["message"])[0]
    assert error_message["code"] == "unique"
    assert error_message["context"]["field"] == "name"


def test_groups_add_duplicated_by_slug(client_query, groups):
    group_name = groups[0].name
    response = client_query(
        """
        mutation addGroup($input: GroupAddMutationInput!){
          addGroup(input: $input) {
            group {
              id
              name
            }
            errors
          }
        }
        """,
        variables={"input": {"name": group_name.upper()}},
    )
    error_result = response.json()["data"]["addGroup"]["errors"][0]
    assert error_result

    error_message = json.loads(error_result["message"])[0]
    assert error_message["code"] == "unique"
    assert error_message["context"]["field"] == "All"


def test_groups_update_by_manager_works(client_query, groups, users):
    old_group = groups[0]
    # Makes sure user is group manager before update
    old_group.add_manager(users[0])

    new_data = {
        "id": str(old_group.id),
        "description": "New description",
        "name": "New Name",
        "website": "https://www.example.com/updated-group",
        "email": "a-new-email@example.com",
        "membershipType": "CLOSED",
    }
    response = client_query(
        """
        mutation updateGroup($input: GroupUpdateMutationInput!) {
          updateGroup(input: $input) {
            group {
              id
              name
              description
              website
              email
              membershipList {
                membershipType
              }
            }
            errors
          }
        }
        """,
        variables={"input": new_data},
    )
    group_result = response.json()["data"]["updateGroup"]["group"]

    assert group_result == {
        "id": str(old_group.id),
        "name": new_data["name"],
        "description": new_data["description"],
        "website": new_data["website"],
        "email": new_data["email"],
        "membershipList": {"membershipType": "CLOSED"},
    }


def test_groups_update_by_member_fails_due_permission_check(client_query, groups):
    old_group = groups[0]
    new_data = {
        "id": str(old_group.id),
        "description": "New description",
    }

    response = client_query(
        """
        mutation updateGroup($input: GroupUpdateMutationInput!) {
          updateGroup(input: $input) {
            group {
              id
            }
            errors
          }
        }
        """,
        variables={"input": new_data},
    )
    response = response.json()

    assert "errors" in response["data"]["updateGroup"]
    assert "update_not_allowed" in response["data"]["updateGroup"]["errors"][0]["message"]


def test_groups_delete_by_manager(client_query, managed_groups):
    old_group = managed_groups[0]

    response = client_query(
        """
        mutation deleteGroup($input: GroupDeleteMutationInput!){
          deleteGroup(input: $input) {
            group {
              slug
            }
          }
        }

        """,
        variables={"input": {"id": str(old_group.id)}},
    )

    group_result = response.json()["data"]["deleteGroup"]["group"]

    assert group_result["slug"] == old_group.slug
    assert not Group.objects.filter(slug=group_result["slug"])


def test_groups_delete_by_non_manager(client_query, groups):
    old_group = groups[0]

    response = client_query(
        """
        mutation deleteGroup($input: GroupDeleteMutationInput!){
          deleteGroup(input: $input) {
            group {
              slug
            }
            errors
          }
        }

        """,
        variables={"input": {"id": str(old_group.id)}},
    )

    response = response.json()

    assert "errors" in response["data"]["deleteGroup"]
    assert "delete_not_allowed" in response["data"]["deleteGroup"]["errors"][0]["message"]


def test_groups_delete_by_anonymous_user(client_query_no_token, groups):
    old_group = groups[0]

    response = client_query_no_token(
        """
        mutation deleteGroup($input: GroupDeleteMutationInput!){
          deleteGroup(input: $input) {
            group {
              slug
            }
            errors
          }
        }

        """,
        variables={"input": {"id": str(old_group.id)}},
    )

    response = response.json()

    assert "errors" in response["data"]["deleteGroup"]
    assert "unauthorized" in response["data"]["deleteGroup"]["errors"][0]["message"]
