from urllib.parse import parse_qs, urlparse

import pytest
from django.core import signing
from django.urls import reverse
from mixer.backend.django import mixer
from oauth2_provider.models import Application

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
