# Copyright © 2026 Technology Matters
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

"""Regression tests for F9: a Django sessionid cookie must not authenticate
API endpoints.  JWT (Authorization: Bearer ...) is the only acceptable
credential for non-public paths."""

from datetime import timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time

from apps.auth.services import JWTService

pytestmark = pytest.mark.django_db


@pytest.fixture
@freeze_time(timezone.now() - timedelta(days=10))
def expired_access_token(user):
    return JWTService().create_access_token(user)


SESSION_BYPASS_PATHS = [
    ("post", "/storage/user-profile-image"),
    ("post", "/storage/landscape-profile-image"),
    ("post", "/shared-data/upload/"),
    ("post", "/story-map/add/"),
    ("post", "/story-map/update/"),
    (
        "get",
        "/export/id/project/00000000-0000-0000-0000-000000000000/probe.json",
    ),
    (
        "get",
        "/export/id/site/00000000-0000-0000-0000-000000000000/probe.json",
    ),
]


@pytest.mark.parametrize("method,path", SESSION_BYPASS_PATHS)
def test_session_cookie_does_not_authenticate_api_endpoint(client, user, method, path):
    """Session cookie + no JWT must yield 401 on every authenticated API path.
    Before the F9 widening, AuthenticationMiddleware would set request.user
    from the session and JWTAuthenticationMiddleware would short-circuit, so
    the request would proceed as the session user — defeating JWT lifecycle."""
    client.force_login(user)
    response = getattr(client, method)(path)
    assert response.status_code == 401, (
        f"{method.upper()} {path} returned {response.status_code} with "
        f"session-only auth; expected 401 (session must not authenticate)."
    )


@pytest.mark.parametrize("method,path", SESSION_BYPASS_PATHS)
def test_session_cookie_with_expired_jwt_returns_401(
    client, user, expired_access_token, method, path
):
    """Session cookie + expired JWT must be rejected by the JWT layer.
    Before the F9 widening, the session would silently authenticate the
    request despite the expired JWT being explicitly attached."""
    client.force_login(user)
    response = getattr(client, method)(
        path,
        HTTP_AUTHORIZATION=f"Bearer {expired_access_token}",
    )
    assert response.status_code == 401


def test_admin_session_unaffected(client, user):
    """Django /admin/ is in PUBLIC_BASE_PATHS and must keep working with
    session auth — only API paths reject session cookies."""
    user.is_staff = True
    user.save()
    client.force_login(user)
    response = client.get("/admin/")
    # /admin/ redirects to /admin/login/ for non-staff but for staff users it
    # serves the admin index (200) — either way it should NOT be 401.
    assert response.status_code != 401


def test_graphql_session_only_request_does_not_create_project(client, user):
    """/graphql/ is auth_optional, so session-only requests aren't 401'd —
    they're treated as anonymous.  Regression for F9: session cookie must not
    let an authenticated mutation through."""
    from apps.project_management.models import Project

    client.force_login(user)
    response = client.post(
        "/graphql/",
        data={
            "query": (
                'mutation { addProject(input: {name: "session-bypass-graphql"}) '
                "{ project { id } errors } }"
            )
        },
        content_type="application/json",
    )
    assert not Project.objects.filter(name="session-bypass-graphql").exists()
    assert "errors" in response.json()


def test_graphql_session_with_expired_jwt_returns_401(client, user, expired_access_token):
    """Session + expired JWT on /graphql/ must be rejected by the JWT layer."""
    client.force_login(user)
    response = client.post(
        "/graphql/",
        data={"query": "query { landscapes { edges { node { slug } } } }"},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {expired_access_token}",
    )
    assert response.status_code == 401
