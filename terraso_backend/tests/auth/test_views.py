import json
from unittest import mock

import pytest
from django.urls import reverse
from httpx import Response

from apps.auth.providers import AppleProvider, GoogleProvider

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


def test_get_google_callback(client, access_tokens_google, respx_mock):
    respx_mock.post(GoogleProvider.GOOGLE_TOKEN_URI).mock(
        return_value=Response(200, json=access_tokens_google)
    )
    url = reverse("terraso_auth:google-callback")
    response = client.get(url, {"code": "testing-code-google-auth"})

    assert response.status_code == 302
    assert response.cookies.get("tokens")


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
    assert response.cookies.get("tokens")


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


def test_post_apple_callback_with_no_user(client):
    url = reverse("terraso_auth:apple-callback")
    response = client.post(url, {"code": "testing-code-apple-auth"})

    assert response.status_code == 400
    assert "couldn't get User name from Apple" in response.content.decode()


def test_post_apple_callback_with_bad_user(client):
    url = reverse("terraso_auth:apple-callback")
    response = client.post(url, {"code": "testing-code-apple-auth", "user": "no-json-content"})

    assert response.status_code == 400
    assert "couldn't parse User data from Apple" in response.content.decode()


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


def test_get_user_information_not_logged_in(client):
    url = reverse("terraso_auth:user")
    response = client.get(url)

    assert response.status_code == 403
    assert "error" in response.json()


def test_get_user_information(client, user, access_token):
    url = reverse("terraso_auth:user")
    response = client.get(url, HTTP_AUTHORIZATION=f"Bearer {access_token}")

    assert response.status_code == 200

    user_data = response.json()["user"]

    assert user_data["email"] == user.email
    assert user_data["first_name"] == user.first_name
    assert user_data["last_name"] == user.last_name
