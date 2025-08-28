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
from unittest import mock
from urllib.parse import parse_qs, urlparse

import pytest
from django.test import override_settings
from django.urls import reverse
from httpx import Response
from mixer.backend.django import mixer
from moto import mock_aws
from oauth2_provider.views import UserInfoView

from apps.auth.providers import AppleProvider, GoogleProvider
from apps.auth.services import JWTService
from apps.auth.views import GoogleCallbackView
from apps.core.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def google_url():
    return reverse("terraso_auth:google-authorize")


@pytest.fixture
def apple_url():
    return reverse("terraso_auth:google-authorize")


@pytest.fixture
def refresh_tokens_url():
    return reverse("terraso_auth:tokens")


def test_get_google_login_url(client, google_url):
    response = client.get(google_url)

    assert response.status_code == 200
    assert "request_url" in response.json()


@mock_aws
def test_get_google_callback(client, access_tokens_google, respx_mock):
    respx_mock.post(GoogleProvider.GOOGLE_TOKEN_URI).mock(
        return_value=Response(200, json=access_tokens_google)
    )
    url = reverse("terraso_auth:google-callback")
    response = client.get(url, {"code": "testing-code-google-auth"})

    assert response.status_code == 302
    assert response.cookies.get("atoken")
    assert response.cookies.get("rtoken")
    assert response.cookies.get("sessionid")


@override_settings(ENV="production")
def test_get_google_callback_evil_redirect_domain_rejected_on_prod(
    client, access_tokens_google, respx_mock
):
    respx_mock.post(GoogleProvider.GOOGLE_TOKEN_URI).mock(
        return_value=Response(200, json=access_tokens_google)
    )
    url = reverse("terraso_auth:google-callback")
    response = client.get(
        url,
        {
            "code": "testing-code-google-auth",
            "state": GoogleCallbackView.encode_state(
                {"origin": "https://evil.com", "redirectUrl": "/gimme-tokens"}
            ),
        },
    )

    assert response.status_code == 400
    assert "Invalid login redirect" in response.content.decode()


def test_get_google_callback_evil_redirect_domain_rejected_by_CORS(
    client, access_tokens_google, respx_mock
):
    respx_mock.post(GoogleProvider.GOOGLE_TOKEN_URI).mock(
        return_value=Response(200, json=access_tokens_google)
    )
    url = reverse("terraso_auth:google-callback")

    response = client.get(
        url,
        {
            "code": "testing-code-google-auth",
            "state": GoogleCallbackView.encode_state(
                {"origin": "https://evil.com", "redirectUrl": "/gimme-tokens"}
            ),
        },
    )

    assert response.status_code == 400
    assert "Invalid login redirect" in response.content.decode()


@override_settings(CORS_ORIGIN_WHITELIST=["https://other.com"])
def test_get_google_callback_redirect_domain_allowed_by_CORS(
    client, access_tokens_google, respx_mock
):
    respx_mock.post(GoogleProvider.GOOGLE_TOKEN_URI).mock(
        return_value=Response(200, json=access_tokens_google)
    )
    url = reverse("terraso_auth:google-callback")

    response = client.get(
        url,
        {
            "code": "testing-code-google-auth",
            "state": GoogleCallbackView.encode_state(
                {"origin": "https://other.com", "redirectUrl": "/tools"}
            ),
        },
    )

    assert response.status_code == 302
    parsed_url = urlparse(response.url)
    assert parsed_url.hostname == "other.com"
    assert parsed_url.path == "/account/auth-callback"
    state = GoogleCallbackView.decode_state(parse_qs(parsed_url.query)["state"][0])
    assert state["redirectUrl"] == "/tools"


@override_settings(CORS_ALLOWED_ORIGIN_REGEXES=["https://.*\.onrender\.com"])
def test_get_google_callback_redirect_domain_allowed_by_CORS_regex(
    client, access_tokens_google, respx_mock
):
    respx_mock.post(GoogleProvider.GOOGLE_TOKEN_URI).mock(
        return_value=Response(200, json=access_tokens_google)
    )
    url = reverse("terraso_auth:google-callback")

    response = client.get(
        url,
        {
            "code": "testing-code-google-auth",
            "state": GoogleCallbackView.encode_state(
                {"origin": "https://test-pr-1.onrender.com", "redirectUrl": "/tools"}
            ),
        },
    )

    assert response.status_code == 302
    parsed_url = urlparse(response.url)
    assert parsed_url.hostname == "test-pr-1.onrender.com"
    assert parsed_url.path == "/account/auth-callback"
    state = GoogleCallbackView.decode_state(parse_qs(parsed_url.query)["state"][0])
    assert state["redirectUrl"] == "/tools"


def test_get_google_callback_without_code(client):
    url = reverse("terraso_auth:google-callback")
    response = client.get(url)

    assert response.status_code == 400
    assert "no authorization code" in response.content.decode()


def test_get_google_callback_with_error(client):
    url = reverse("terraso_auth:google-callback")
    response = client.get(url, {"error": "Bad Request: authentication failed"})

    assert response.status_code == 400
    assert "Bad Request: authentication failed" in response.content.decode()


def test_get_apple_login_url(client, apple_url):
    response = client.get(apple_url)

    assert response.status_code == 200
    assert "request_url" in response.json()


@mock_aws
def test_post_apple_callback(client, access_tokens_apple, respx_mock):
    respx_mock.post(AppleProvider.TOKEN_URI).mock(
        return_value=Response(200, json=access_tokens_apple)
    )
    url = reverse("terraso_auth:apple-callback")

    with mock.patch("apps.auth.providers.AppleProvider._build_client_secret"):
        response = client.post(
            url,
            {
                "code": "testing-code-apple-auth",
                "user": json.dumps(
                    {
                        "name": {"firstName": "Testing", "lastName": "Terraso"},
                        "email": "testingterraso@example.org",
                    }
                ),
            },
        )

    assert response.status_code == 302
    assert response.cookies.get("atoken")
    assert response.cookies.get("rtoken")
    assert response.cookies.get("sessionid")


def test_post_apple_callback_without_code(client):
    url = reverse("terraso_auth:apple-callback")
    response = client.post(url)

    assert response.status_code == 400
    assert "no authorization code" in response.content.decode()


def test_post_apple_callback_with_error(client):
    url = reverse("terraso_auth:apple-callback")
    response = client.post(url, {"error": "Bad Request: authentication failed"})

    assert response.status_code == 400
    assert "Bad Request: authentication failed" in response.content.decode()


@mock_aws
def test_post_apple_callback_with_no_user(client, access_tokens_apple, respx_mock):
    respx_mock.post(AppleProvider.TOKEN_URI).mock(
        return_value=Response(200, json=access_tokens_apple)
    )
    url = reverse("terraso_auth:apple-callback")

    with mock.patch("apps.auth.providers.AppleProvider._build_client_secret"):
        response = client.post(url, {"code": "testing-code-apple-auth"})

    assert response.status_code == 302, response.content
    assert response.cookies.get("atoken")
    assert response.cookies.get("rtoken")
    assert response.cookies.get("sessionid")


@mock_aws
def test_post_apple_callback_nth_login(client, access_tokens_apple, respx_mock):
    # This is simulating a user already signed up
    user = mixer.blend(
        User, email="testingterraso@example.com", first_name="Testing", last_name="Terraso"
    )

    respx_mock.post(AppleProvider.TOKEN_URI).mock(
        return_value=Response(200, json=access_tokens_apple)
    )
    url = reverse("terraso_auth:apple-callback")

    with mock.patch("apps.auth.providers.AppleProvider._build_client_secret"):
        # After first login Apple stop sending user names
        response = client.post(
            url,
            {"code": "testing-code-apple-auth"},
        )

    assert response.status_code == 302

    user.refresh_from_db()

    # Even without receiving user names from Apple, we should keep the original user names
    assert user.first_name == "Testing"
    assert user.last_name == "Terraso"


def test_post_apple_callback_with_bad_user(client):
    url = reverse("terraso_auth:apple-callback")
    response = client.post(url, {"code": "testing-code-apple-auth", "user": "no-json-content"})

    assert response.status_code == 400
    assert "Couldn't parse User data from Apple" in response.content.decode()


def test_post_refresh_token_without_token(client, refresh_tokens_url, refresh_token):
    response = client.post(
        refresh_tokens_url, data={"refresh_token": ""}, content_type="application/json"
    )

    assert response.status_code == 400
    assert "error" in response.json()


def test_post_refresh_token_successfully(client, refresh_tokens_url, refresh_token):
    response = client.post(
        refresh_tokens_url, data={"refresh_token": refresh_token}, content_type="application/json"
    )

    assert response.status_code == 200

    tokens_data = response.json()

    assert "access_token" in tokens_data
    assert "refresh_token" in tokens_data


def test_post_refresh_token_expired_token(client, refresh_tokens_url, expired_refresh_token):
    response = client.post(
        refresh_tokens_url,
        data={"refresh_token": expired_refresh_token},
        content_type="application/json",
    )

    assert response.status_code == 400

    tokens_data = response.json()

    assert tokens_data["error"] == "Signature has expired"


def test_post_refresh_token_deleted_user(client, refresh_tokens_url, user, refresh_token):
    user.delete()

    response = client.post(
        refresh_tokens_url, data={"refresh_token": refresh_token}, content_type="application/json"
    )

    assert response.status_code == 400

    tokens_data = response.json()

    assert tokens_data["error"] == "User not found"


def test_post_refresh_token_inactive_user(client, refresh_tokens_url, user, refresh_token):
    user.is_active = False
    user.save()

    response = client.post(
        refresh_tokens_url, data={"refresh_token": refresh_token}, content_type="application/json"
    )

    assert response.status_code == 400

    tokens_data = response.json()
    assert tokens_data["error"] == "User not found"


@pytest.fixture
def bearer_header(access_token):
    return ("HTTP_AUTHORIZATION", "Bearer " + access_token)


def test_userinfo_claims(rf, bearer_header, user):
    req = rf.get(reverse("oauth2_provider:user-info"), **dict([bearer_header]))
    req.user = user
    resp = UserInfoView.as_view()(req)
    assert resp.status_code == 200
    resp_json = json.loads(resp.content)
    assert resp_json["email"] == user.email


@mock_aws
def test_sign_up_is_first_login(client, access_tokens_google, respx_mock):
    respx_mock.post(GoogleProvider.GOOGLE_TOKEN_URI).mock(
        return_value=Response(200, json=access_tokens_google)
    )
    url = reverse("terraso_auth:google-callback")
    response = client.get(url, {"code": "testing-code-google-auth"})

    token = response.cookies.get("atoken")

    decoded_payload = JWTService().verify_access_token(token.value)

    assert decoded_payload["isFirstLogin"] is True
