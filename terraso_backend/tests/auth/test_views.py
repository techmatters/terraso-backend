import pytest
from django.urls import reverse
from httpx import Response

from apps.auth.providers import GoogleProvider

pytestmark = pytest.mark.django_db


@pytest.fixture
def google_url():
    return reverse("terraso_auth:google-authorize")


@pytest.fixture
def apple_url():
    return reverse("terraso_auth:google-authorize")


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

    auth_cookie = response.cookies.get("user")
    assert auth_cookie
    assert "testingterraso@example.com" in auth_cookie.value


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


def test_post_apple_authorize_no_json_request(client, apple_url):
    response = client.post(apple_url, data={})

    assert response.status_code == 400
    assert "error" in response.json()


def test_post_apple_authorize_without_code(client, apple_url):
    response = client.post(apple_url, data={}, content_type="application/json")

    assert response.status_code == 400
    assert "error" in response.json()
