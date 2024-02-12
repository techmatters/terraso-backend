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

import pytest
from django.urls import reverse
from httpx import Response
from mixer.backend.django import mixer
from moto import mock_aws

from apps.auth.providers import GoogleProvider
from apps.collaboration.models import Membership

pytestmark = pytest.mark.django_db


@pytest.fixture
def access_tokens_google():
    """
    Mocked data received from Google.
    User name: Testing Terraso
    User email: testingterraso@example.com
    """
    return {
        "access_token": "opaque-access-token",
        "expires_in": 3599,
        "refresh_token": "opaque-refresh-token",
        "scope": "openid https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile",  # noqa
        "token_type": "Bearer",
        "id_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL2FjY291bnRzLmdvb2dsZS5jb20iLCJhenAiOiI4ODYwOTkzMTgyNzQtNDN2bGdmaGlmdDk1YWdncGgxdGRyc2VsM2tuNW1wbTAuYXBwcy5nb29nbGV1c2VyY29udGVudC5jb20iLCJhdWQiOiI4ODYwOTkzODI3NC00M3ZsZ2ZoaWZ0OTVhZ2dwaDF0ZHJzZWwza241bXBtMC5hcHBzLmdvb2dsZXVzZXJjb250ZW50LmNvbSIsInN1YiI6IjEwODkzMTgyNzQ3NzM4MjgwMjkiLCJlbWFpbCI6InRlc3Rpbmd0ZXJyYXNvQGV4YW1wbGUuY29tIiwiZW1haWxfdmVyaWZpZWQiOnRydWUsImF0X2hhc2giOiJkcnpRcjFpUzFoQ1BYcGtFeHdzMDZnIiwibmFtZSI6IlRlc3RpbmcgVGVycmFzbyIsInBpY3R1cmUiOiJodHRwczovL2xoMy5nb29nbGV1c2VyY29udGVudC5jb20vYS0vYWFhSkpKbmV4am5uZG1mTVE3b2RqUFAyWDAzbVV6WVNaLWNSd0kzbjJXNEFRPXM5Ni1jIiwiZ2l2ZW5fbmFtZSI6IlRlc3RpbmciLCJmYW1pbHlfbmFtZSI6IlRlcnJhc28iLCJsb2NhbGUiOiJlbiIsImlhdCI6MTYzOTQxNjAyNywiZXhwIjoxNjM5NDE5NjI3fQ.fXj-d9GJ8E9IQnML7F1iAPFeRIyBQ4GEu_OC3tJlKCM",  # noqa
    }


@pytest.fixture
def pending_membership_not_registered_mixed_case_email():
    return mixer.blend(Membership, pending_email="TestingTerraso@example.com", user=None)


@pytest.fixture
def pending_membership_not_registered_lowercase_email():
    return mixer.blend(Membership, pending_email="testingterraso@example.com", user=None)


@mock_aws
def test_signup_signal_membership_update_with_mixed_case_email(
    client, access_tokens_google, pending_membership_not_registered_mixed_case_email, respx_mock
):
    membership = Membership.objects.get(id=pending_membership_not_registered_mixed_case_email.id)
    assert membership.user is None

    respx_mock.post(GoogleProvider.GOOGLE_TOKEN_URI).mock(
        return_value=Response(200, json=access_tokens_google)
    )
    url = reverse("terraso_auth:google-callback")
    response = client.get(url, {"code": "testing-code-google-auth"})

    assert response.status_code == 302

    membership = Membership.objects.get(id=pending_membership_not_registered_mixed_case_email.id)
    assert membership.user is not None


@mock_aws
def test_signup_signal_membership_update_with_lowercase_email(
    client, access_tokens_google, pending_membership_not_registered_lowercase_email, respx_mock
):
    membership = Membership.objects.get(id=pending_membership_not_registered_lowercase_email.id)
    assert membership.user is None

    respx_mock.post(GoogleProvider.GOOGLE_TOKEN_URI).mock(
        return_value=Response(200, json=access_tokens_google)
    )
    url = reverse("terraso_auth:google-callback")
    response = client.get(url, {"code": "testing-code-google-auth"})

    assert response.status_code == 302

    membership = Membership.objects.get(id=pending_membership_not_registered_lowercase_email.id)
    assert membership.user is not None
