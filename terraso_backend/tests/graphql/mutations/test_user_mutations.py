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
          }
        }
        """,
        variables={"input": new_data},
    )
    response = response.json()

    assert "errors" in response
    assert "update_not_allowed" in response["errors"][0]["message"]


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
          }
        }
        """,
        variables={"input": {"id": str(old_user.id)}},
    )
    response = response.json()

    assert "errors" in response
    assert "delete_not_allowed" in response["errors"][0]["message"]


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
          }
        }
        """,
        variables={"input": {"userEmail": str(old_user.email), "key": "key1", "value": "value1"}},
    )
    response = response.json()

    assert "errors" in response
    assert "update_not_allowed" in response["errors"][0]["message"]


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
        variables={"input": {"userEmail": str(old_user.email), "key": "key1"}},
    )
    response = response.json()

    assert "errors" in response
    assert "delete_not_allowed" in response["errors"][0]["message"]
