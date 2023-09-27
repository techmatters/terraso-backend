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
from graphene_django.utils.testing import graphql_query

from apps.auth.services import JWTService

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(users):
    return users[0]


@pytest.fixture
def access_token(user):
    return JWTService().create_access_token(user)


@pytest.fixture
def test_access_token(user):
    return JWTService().create_test_access_token(user)


@pytest.fixture
def invalid_access_token(user):
    return JWTService().create_token(user)


@pytest.fixture
def token_client_query(client):
    def _client_query(token, *args, **kwargs):
        headers = {
            "CONTENT_TYPE": "application/json",
            "HTTP_AUTHORIZATION": f"Bearer {token}",
        }
        return graphql_query(*args, **kwargs, headers=headers, client=client)

    return _client_query


def execute_query(token_client_query, user, token):
    query = (
        """
        {users(email: "%s") {
            edges {
            node {
                email
            }
            }
        }}
        """
        % user.email
    )
    response = token_client_query(token, query)
    return response.json()


def test_access_token_valid(token_client_query, user, access_token):
    response = execute_query(token_client_query, user, access_token)
    user_result = response["data"]["users"]["edges"][0]["node"]
    assert user_result["email"] == user.email


def test_test_access_token_valid(token_client_query, user, test_access_token):
    response = execute_query(token_client_query, user, test_access_token)
    user_result = response["data"]["users"]["edges"][0]["node"]
    assert user_result["email"] == user.email


def test_access_token_invalid(token_client_query, user, invalid_access_token):
    response = execute_query(token_client_query, user, invalid_access_token)
    assert response["error"] == "Unauthorized request"
