import pytest
from httpx import Response

from apps.auth.providers import GoogleProvider
from apps.auth.services import AccountService

pytestmark = pytest.mark.django_db


def test_sign_up_with_google_creates_user(respx_mock, access_tokens_google):
    respx_mock.post(GoogleProvider.GOOGLE_TOKEN_URI).mock(
        return_value=Response(200, json=access_tokens_google)
    )
    service = AccountService()

    user = service.sign_up_with_google("authorization_code")

    assert user

    assert user.email == "testingterraso@example.com"
