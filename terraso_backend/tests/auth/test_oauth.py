# Copyright © 2023 Technology Matters
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

from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore
from django.core import signing
from django.http import HttpResponse, HttpResponseRedirect
from django.test import RequestFactory
from django.urls import reverse
from mixer.backend.django import mixer
from oauth2_provider.models import Application

from apps.auth.constants import SESSION_FLAG_OAUTH_LOGIN
from apps.auth.middleware import OAuthAuthorizeState
from apps.auth.views import terraso_login

pytestmark = pytest.mark.django_db


@pytest.fixture
def oauth_application():
    return mixer.blend(Application)


@pytest.mark.parametrize("logged_in", [False, True])
def test_unauthenticated_user_accessing_auth_point_gets_cookie_set(
    client, oauth_application, user, logged_in
):
    authorize_url = reverse("oauth2_provider:authorize")
    params = dict(
        response_type=["code"],
        client_id=[oauth_application.client_id],
        redirect_url=["https://example.org/callback"],
    )
    if logged_in:
        client.force_login(user)
    resp = client.get(authorize_url, params)
    if not logged_in:
        assert (cookie := resp.cookies.get("oauth", None))
        # default salt is the key
        signer = signing.get_cookie_signer(salt="oauth")
        url = urlparse(signer.unsign(cookie.value))
        assert url.path == authorize_url
        assert parse_qs(url.query) == params
    else:
        assert "oauth" not in resp.cookies


def test_other_route_does_not_get_cookie(client):
    url = "/foo"
    resp = client.get(url)
    assert "oauth" not in resp.cookies


# --- Session-flush-on-grant-completion (defense-in-depth follow-up to F9) ---
#
# `terraso_login()` creates a Django session that exists only to round-trip
# the user through /oauth/authorize.  Once the grant is emitted, the session
# has no further purpose; OAuthAuthorizeState flushes it so the cookie
# doesn't linger for the default SESSION_COOKIE_AGE.
#
# The flush is gated on a session-key marker so non-OAuth-flow sessions
# (e.g. Django admin) are untouched.


def test_terraso_login_sets_oauth_session_marker(user):
    """terraso_login marks the session so OAuthAuthorizeState knows the
    session was created for the OAuth flow (vs. e.g. admin login)."""
    rf = RequestFactory()
    request = rf.get("/auth/google/callback")
    request.session = SessionStore()

    terraso_login(request, user)

    assert request.session.get(SESSION_FLAG_OAUTH_LOGIN) is True


def _build_request_to_authorize(user, session_data=None):
    rf = RequestFactory()
    request = rf.get(reverse("oauth2_provider:authorize"))
    request.user = user
    request.session = SessionStore()
    for k, v in (session_data or {}).items():
        request.session[k] = v
    request.session.save()
    return request


def _run_oauth_middleware(request, response):
    middleware = OAuthAuthorizeState(lambda req: response)
    return middleware(request)


def test_middleware_flushes_session_on_successful_grant_with_marker(user):
    """Successful grant (302 to redirect_uri carrying ?code=...) AND marker
    present → session is flushed."""
    request = _build_request_to_authorize(
        user, session_data={SESSION_FLAG_OAUTH_LOGIN: True, "_auth_user_id": str(user.pk)}
    )
    assert request.session.session_key is not None

    grant_response = HttpResponseRedirect("https://client.example.com/cb?code=AAA&state=xyz")
    _run_oauth_middleware(request, grant_response)

    assert request.session.session_key is None
    assert SESSION_FLAG_OAUTH_LOGIN not in request.session


def test_middleware_flushes_on_id_token_redirect(user):
    """Implicit/hybrid flow uses ?id_token=... instead of ?code=...; same flush."""
    request = _build_request_to_authorize(user, session_data={SESSION_FLAG_OAUTH_LOGIN: True})

    grant_response = HttpResponseRedirect("https://client.example.com/cb?id_token=eyJabc&state=xyz")
    _run_oauth_middleware(request, grant_response)

    assert request.session.session_key is None


def test_middleware_does_not_flush_session_without_marker(user):
    """Admin-style session (no marker): even on a grant-style redirect,
    the session must survive."""
    request = _build_request_to_authorize(
        user, session_data={"_auth_user_id": str(user.pk), "admin_thing": "preserved"}
    )
    original_key = request.session.session_key
    assert original_key is not None

    grant_response = HttpResponseRedirect("https://client.example.com/cb?code=AAA")
    _run_oauth_middleware(request, grant_response)

    assert request.session.session_key == original_key
    assert request.session["admin_thing"] == "preserved"


def test_middleware_does_not_flush_on_error_redirect(user):
    """Error redirects (?error=access_denied) are not grant emissions; preserve session."""
    request = _build_request_to_authorize(user, session_data={SESSION_FLAG_OAUTH_LOGIN: True})
    original_key = request.session.session_key

    error_response = HttpResponseRedirect(
        "https://client.example.com/cb?error=access_denied&state=xyz"
    )
    _run_oauth_middleware(request, error_response)

    assert request.session.session_key == original_key
    assert request.session.get(SESSION_FLAG_OAUTH_LOGIN) is True


def test_middleware_does_not_flush_on_non_redirect_response(user):
    """Consent page (200), error page (200), etc. → preserve session.
    Only a real redirect with code/id_token triggers flush."""
    request = _build_request_to_authorize(user, session_data={SESSION_FLAG_OAUTH_LOGIN: True})
    original_key = request.session.session_key

    consent_response = HttpResponse("<consent form>", status=200)
    _run_oauth_middleware(request, consent_response)

    assert request.session.session_key == original_key


def test_middleware_does_not_flush_on_unrelated_path(user, oauth_application):
    """Requests to paths other than /oauth/authorize must not flush sessions
    even if marker is present and response happens to look like a grant."""
    rf = RequestFactory()
    request = rf.get("/some/other/path")
    request.user = user
    request.session = SessionStore()
    request.session[SESSION_FLAG_OAUTH_LOGIN] = True
    request.session.save()
    original_key = request.session.session_key

    response = HttpResponseRedirect("https://elsewhere.example.com/?code=AAA")
    _run_oauth_middleware(request, response)

    assert request.session.session_key == original_key
    assert request.session.get(SESSION_FLAG_OAUTH_LOGIN) is True


def test_middleware_anonymous_branch_still_sets_oauth_cookie(client, oauth_application):
    """Regression: the original anonymous-user return-URL cookie behavior
    must not break when we add the authenticated-flush branch."""
    authorize_url = reverse("oauth2_provider:authorize")
    params = dict(
        response_type=["code"],
        client_id=[oauth_application.client_id],
        redirect_url=["https://example.org/callback"],
    )
    resp = client.get(authorize_url, params)
    assert (cookie := resp.cookies.get("oauth", None))
    signer = signing.get_cookie_signer(salt="oauth")
    url = urlparse(signer.unsign(cookie.value))
    assert url.path == authorize_url


def test_middleware_anonymous_with_redirect_does_not_flush(client):
    """An anonymous user hitting /oauth/authorize gets a redirect — but
    without a session-marker, the flush path must not fire."""
    rf = RequestFactory()
    request = rf.get(reverse("oauth2_provider:authorize"))
    request.user = AnonymousUser()
    request.session = SessionStore()
    request.session.save()
    original_key = request.session.session_key

    # Simulate the response the existing middleware would set the cookie on.
    response = HttpResponse(status=302)
    _run_oauth_middleware(request, response)

    # Anonymous branch sets the oauth-return cookie but must not touch session.
    assert request.session.session_key == original_key
