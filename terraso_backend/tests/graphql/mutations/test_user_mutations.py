import pytest
from graphene_django.utils.testing import graphql_query

from apps.core.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def client_query(client):
    def _client_query(*args, **kwargs):
        return graphql_query(*args, **kwargs, client=client)

    return _client_query


def test_users_add(client_query):
    user_email = "Testing User"
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
    old_user = _get_users(client_query)[0]
    new_data = {
        "id": old_user["id"],
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


def test_users_delete(client_query, users):
    old_user = _get_users(client_query)[0]
    response = client_query(
        """
        mutation deleteUser($input: UserDeleteMutationInput!){
          deleteUser(input: $input) {
            user {
              id
              email
            }
          }
        }
        """,
        variables={"input": {"id": old_user["id"]}},
    )

    user_result = response.json()["data"]["deleteUser"]["user"]

    assert user_result["email"] == old_user["email"]
    assert not User.objects.filter(email=user_result["email"])


def _get_users(client_query):
    response = client_query(
        """
        {
          users {
            edges {
              node {
                id
                email
              }
            }
          }
        }
        """
    )
    edges = response.json()["data"]["users"]["edges"]
    return [e["node"] for e in edges]
