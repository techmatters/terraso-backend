from unittest import mock

import pytest
from httpx import Response

from apps.auth.exceptions import ExpiredTokenError
from apps.auth.providers import AppleProvider, GoogleProvider
from apps.auth.services import AccountService, JWTService

pytestmark = pytest.mark.django_db


def test_sign_up_with_google_creates_user(respx_mock, access_tokens_google):
    respx_mock.post(GoogleProvider.GOOGLE_TOKEN_URI).mock(
        return_value=Response(200, json=access_tokens_google)
    )
    service = AccountService()

    user = service.sign_up_with_google("authorization_code")

    assert user

    assert user.email == "testingterraso@example.com"


def test_sign_up_with_apple_creates_user(respx_mock, access_tokens_apple):
    respx_mock.post(AppleProvider.TOKEN_URI).mock(
        return_value=Response(200, json=access_tokens_apple)
    )
    service = AccountService()

    with mock.patch("apps.auth.providers.AppleProvider._build_client_secret") as mock_secret:
        mock_secret.return_value = "mocked-secret-value"
        user = service.sign_up_with_apple(
            "authorization_code", first_name="Testing", last_name="Terraso"
        )

    mock_secret.assert_called_once()

    assert user

    assert user.email == "testingterraso@example.com"
    assert user.first_name == "Testing"
    assert user.last_name == "Terraso"


def test_verify_valid_token(user, access_token):
    jwt_service = JWTService()

    token = jwt_service.verify_token(access_token)

    assert token["sub"] == str(user.id)
    assert token["email"] == user.email


def test_verify_expired_token_raises_exception(expired_access_token):
    jwt_service = JWTService()

    with pytest.raises(ExpiredTokenError):
        jwt_service.verify_token(expired_access_token)
