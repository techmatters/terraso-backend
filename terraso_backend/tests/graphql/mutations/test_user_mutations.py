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

from apps.core.models import User

pytestmark = pytest.mark.django_db


def test_users_add(client_query):
    user_email = "testinuser@example.com"
    user_password = "123456"
    response = client_query(
        """
        mutation addUser($input: UserAddMutationInput!){
          addUser(input: $input) {
            user {
              id
              email
            }
          }
        }
        """,
        variables={"input": {"email": user_email, "password": user_password}},
    )
    user_result = response.json()["data"]["addUser"]["user"]

    assert user_result["id"]
    assert user_result["email"] == user_email


def test_users_update(client_query, users):
    old_user = users[0]
    new_data = {
        "id": str(old_user.id),
        "firstName": "Tina",
        "lastName": "Testing",
        "email": "tinatesting@example.com",
        "password": "mynewsafepass",
    }
    response = client_query(
        """
        mutation updateUser($input: UserUpdateMutationInput!) {
          updateUser(input: $input) {
            user {
              id
              firstName
              lastName
              email
            }
          }
        }
        """,
        variables={"input": new_data},
    )
    user_result = response.json()["data"]["updateUser"]["user"]
    del new_data["password"]

    assert user_result == new_data


def test_users_update_by_other_user_fail(client_query, users):
    old_user = users[1]
    new_data = {
        "id": str(old_user.id),
        "email": "tinatesting@example.com",
    }
    response = client_query(
        """
        mutation updateUser($input: UserUpdateMutationInput!) {
          updateUser(input: $input) {
            user {
              email
            }
            errors
          }
        }
        """,
        variables={"input": new_data},
    )
    response = response.json()

    assert "errors" in response["data"]["updateUser"]
    assert "update_not_allowed" in response["data"]["updateUser"]["errors"][0]["message"]


def test_users_delete(client_query, users):
    old_user = users[0]
    response = client_query(
        """
        mutation deleteUser($input: UserDeleteMutationInput!){
          deleteUser(input: $input) {
            user {
              email
            }
          }
        }
        """,
        variables={"input": {"id": str(old_user.id)}},
    )

    user_result = response.json()["data"]["deleteUser"]["user"]

    assert user_result["email"] == old_user.email
    assert not User.objects.filter(email=user_result["email"])


def test_users_delete_by_other_user_fail(client_query, users):
    old_user = users[1]
    response = client_query(
        """
        mutation deleteUser($input: UserDeleteMutationInput!){
          deleteUser(input: $input) {
            user {
              email
            }
            errors
          }
        }
        """,
        variables={"input": {"id": str(old_user.id)}},
    )
    response = response.json()

    assert "errors" in response["data"]["deleteUser"]
    assert "delete_not_allowed" in response["data"]["deleteUser"]["errors"][0]["message"]


def test_users_preference_update(client_query, users):
    old_user = users[0]
    response = client_query(
        """
        mutation updateUserPreference($input: UserPreferenceUpdateInput!){
          updateUserPreference(input: $input) {
            preference {
              key
              value
            }
          }
        }
        """,
        variables={
            "input": {
                "userEmail": str(old_user.email),
                "key": "language",
                "value": "es-EC",
            }
        },
    )

    result = response.json()["data"]["updateUserPreference"]["preference"]

    assert result["key"] == "language"
    assert result["value"] == "es-EC"


def test_users_preference_update_by_other_fail(client_query, users):
    old_user = users[1]
    response = client_query(
        """
        mutation updateUserPreference($input: UserPreferenceUpdateInput!){
          updateUserPreference(input: $input) {
            preference {
              key
              value
            }
            errors
          }
        }
        """,
        variables={"input": {"userEmail": str(old_user.email), "key": "key1", "value": "value1"}},
    )
    response = response.json()

    assert "errors" in response["data"]["updateUserPreference"]
    assert "update_not_allowed" in response["data"]["updateUserPreference"]["errors"][0]["message"]


def test_users_preference_delete(client_query, users):
    old_user = users[0]
    client_query(
        """
        mutation updateUserPreference($input: UserPreferenceUpdateInput!){
          updateUserPreference(input: $input) {
            preference {
              key
              value
            }
          }
        }
        """,
        variables={
            "input": {
                "userEmail": str(old_user.email),
                "key": "language",
                "value": "es-EC",
            }
        },
    )
    response = client_query(
        """
        mutation deleteUserPreference($input: UserPreferenceDeleteInput!){
          deleteUserPreference(input: $input) {
            preference {
              key
              value
            }
          }
        }
        """,
        variables={
            "input": {
                "userEmail": str(old_user.email),
                "key": "language",
            }
        },
    )

    result = response.json()["data"]["deleteUserPreference"]["preference"]

    assert result["key"] == "language"
    assert result["value"] == "es-EC"


def test_users_preference_delete_by_other_fail(client_query, users):
    old_user = users[1]
    client_query(
        """
    mutation updateUserPreference($input: UserPreferenceUpdateInput!){
      updateUserPreference(input: $input) {
        preference {
          key
          value
        }
      }
    }
    """,
        variables={
            "input": {
                "userEmail": str(old_user.email),
                "key": "language",
                "value": "es-EC",
            }
        },
    )
    response = client_query(
        """
        mutation deleteUserPreference($input: UserPreferenceDeleteInput!){
          deleteUserPreference(input: $input) {
            preference {
              key
              value
            }
            errors
          }
        }
        """,
        variables={"input": {"userEmail": str(old_user.email), "key": "language"}},
    )
    response = response.json()

    assert "errors" in response["data"]["deleteUserPreference"]
    assert "delete_not_allowed" in response["data"]["deleteUserPreference"]["errors"][0]["message"]


def test_users_unsubscribe_update(
    client_query_no_token, users_with_group_notifications, unsubscribe_token
):
    assert (
        "true" == users_with_group_notifications[0].preferences.filter(key="notifications")[0].value
    )

    response = client_query_no_token(
        """
    mutation unsubscribeUser($input: UserUnsubscribeUpdateInput!) {
      unsubscribeUser(input: $input) {
        errors
      }
    }
    """,
        variables={"input": {"token": unsubscribe_token}},
    )
    response = response.json()

    assert "errors" in response["data"]["unsubscribeUser"]
    assert response["data"]["unsubscribeUser"]["errors"] is None
    assert (
        "false"
        == users_with_group_notifications[0].preferences.filter(key="notifications")[0].value
    )


def test_users_unsubscribe_update_fail(client_query_no_token):
    response = client_query_no_token(
        """
    mutation unsubscribeUser($input: UserUnsubscribeUpdateInput!) {
      unsubscribeUser(input: $input) {
        errors
      }
    }
    """,
        variables={"input": {"token": "123456"}},
    )
    response = response.json()

    assert "errors" in response["data"]["unsubscribeUser"]
    assert "update_not_allowed" in response["data"]["unsubscribeUser"]["errors"][0]["message"]
