import pytest
from django.urls import reverse


@pytest.fixture
def url():
    return reverse("terraso_auth:google-authorize")


def test_get_google_login_url(client, url):
    response = client.get(url)

    assert response.status_code == 200
    assert "request_url" in response.json()


def test_post_google_authorize_no_json_request(client, url):
    response = client.post(url, data={})

    assert response.status_code == 400
    assert "error" in response.json()


def test_post_google_authorize_without_code(client, url):
    response = client.post(url, data={}, content_type="application/json")

    assert response.status_code == 400
    assert "error" in response.json()
