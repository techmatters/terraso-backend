import pytest
from django.urls import reverse


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


def test_post_google_authorize_no_json_request(client, google_url):
    response = client.post(google_url, data={})

    assert response.status_code == 400
    assert "error" in response.json()


def test_post_google_authorize_without_code(client, google_url):
    response = client.post(google_url, data={}, content_type="application/json")

    assert response.status_code == 400
    assert "error" in response.json()


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
