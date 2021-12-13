import pytest
from django.utils import timezone
from httpx import Response

from apps.auth.models import Authorization
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


def test_sign_up_with_google_creates_authorization(respx_mock, access_tokens_google):
    respx_mock.post(GoogleProvider.GOOGLE_TOKEN_URI).mock(
        return_value=Response(200, json=access_tokens_google)
    )
    user = AccountService().sign_up_with_google("authorization_code")

    assert Authorization.objects.count() == 1

    authorization = Authorization.objects.get(user=user)

    assert authorization.access_token == access_tokens_google["access_token"]
    assert authorization.refresh_token == access_tokens_google["refresh_token"]
    assert authorization.expires_at > timezone.now()
