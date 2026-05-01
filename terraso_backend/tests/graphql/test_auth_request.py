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


def test_graphql_query_with_expired_token_returns_401_error_when_debug_is_off(
    settings, expired_client_query
):
    settings.DEBUG = False

    response = expired_client_query(
        """
        query {
            landscapes {
                edges {
                    node {
                        slug
                    }
                }
            }
        }
        """
    )
    assert response.status_code == 401
    assert "error" in response.json()


def test_graphql_query_with_expired_token_returns_not_ok_when_debug_is_on(
    settings, expired_client_query
):
    settings.DEBUG = True

    response = expired_client_query(
        """
        query {
            landscapes {
                edges {
                    node {
                        slug
                    }
                }
            }
        }
        """
    )
    assert response.status_code == 401


def test_graphql_query_without_token_returns_ok(client_query_no_token, landscapes):
    response = client_query_no_token(
        """
        query {
            landscapes {
                edges {
                    node {
                        slug
                    }
                }
            }
        }
        """
    )
    assert response.status_code == 200
    assert response.json()["data"]["landscapes"]["edges"][0]["node"]["slug"] == landscapes[0].slug


def test_graphql_session_cookie_is_ignored(client, user):
    """A Django session cookie must NOT authenticate /graphql/ requests.
    Only the JWT (Authorization: Bearer ...) is accepted as an API credential.
    Regression test for F9 in scripts/security_audit_findings.md."""
    from apps.project_management.models import Project

    client.force_login(user)
    response = client.post(
        "/graphql/",
        data={
            "query": (
                'mutation { addProject(input: {name: "session-bypass-probe"}) '
                "{ project { id } errors } }"
            )
        },
        content_type="application/json",
    )
    # The mutation must not have created a project — the session cookie alone
    # must not authenticate the request.
    assert not Project.objects.filter(name="session-bypass-probe").exists()
    assert "errors" in response.json()


def test_graphql_session_cookie_with_expired_jwt_returns_401(
    client, user, expired_access_token
):
    """Session cookie + expired JWT must be rejected by the JWT layer.
    Before the F9 fix, the session would short-circuit and let the request
    through despite the expired JWT."""
    client.force_login(user)
    response = client.post(
        "/graphql/",
        data={"query": "query { landscapes { edges { node { slug } } } }"},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {expired_access_token}",
    )
    assert response.status_code == 401
    assert "error" in response.json()


def test_graphql_session_cookie_with_valid_jwt_authenticates_as_jwt_user(
    client, user, access_token
):
    """Valid JWT wins regardless of session cookie presence."""
    client.force_login(user)
    response = client.post(
        "/graphql/",
        data={"query": "query { landscapes { edges { node { slug } } } }"},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
    )
    assert response.status_code == 200
    assert "errors" not in response.json()
