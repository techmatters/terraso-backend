from unittest import mock

import pytest
from httpx import Response
from mixer.backend.django import mixer
from moto import mock_s3

from apps.auth.providers import AppleProvider, GoogleProvider
from apps.auth.services import AccountService
from apps.core.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    first_name, last_name = "User", "Testing"
    return mixer.blend(
        User, first_name=first_name, last_name=last_name, email="testingterraso@example.com"
    )


@mock_s3
@mock.patch("urllib.request.urlopen", mock.mock_open(read_data="file content"))
@mock.patch("apps.storage.services.ProfileImageService.upload_url")
def test_sign_up_with_google_creates_user(mock_upload, respx_mock, access_tokens_google):
    mock_upload.return_value = "https://test.com/user-id/image-path"
    respx_mock.post(GoogleProvider.GOOGLE_TOKEN_URI).mock(
        return_value=Response(200, json=access_tokens_google)
    )
    service = AccountService()
    user = service.sign_up_with_google("authorization_code")

    assert user

    assert user.email == "testingterraso@example.com"
    mock_upload.assert_called_once()


def test_sign_in_with_google_doesnt_update_user_names(respx_mock, access_tokens_google, user):
    respx_mock.post(GoogleProvider.GOOGLE_TOKEN_URI).mock(
        return_value=Response(200, json=access_tokens_google)
    )
    service = AccountService()

    user_result = service.sign_up_with_google("authorization_code")

    assert user_result.email == user.email
    assert user_result.last_name == user.last_name
    assert user_result.first_name == user.first_name


@mock_s3
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


def test_sign_in_with_apple_doesnt_update_user_names(respx_mock, access_tokens_apple, user):
    respx_mock.post(AppleProvider.TOKEN_URI).mock(
        return_value=Response(200, json=access_tokens_apple)
    )
    service = AccountService()

    with mock.patch("apps.auth.providers.AppleProvider._build_client_secret") as mock_secret:
        mock_secret.return_value = "mocked-secret-value"
        user_result = service.sign_up_with_apple(
            "authorization_code", first_name="Testing", last_name="Terraso"
        )

    assert user_result.email == user.email
    assert user_result.first_name == user.first_name
    assert user_result.last_name == user.last_name
