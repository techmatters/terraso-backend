import base64
import json
import math
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.auth.services import JWTService

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def private_key(scope="session"):
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def other_private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def get_public_numbers(private_key):
    pubnum = private_key.public_key().public_numbers()
    return pubnum.e, pubnum.n


@pytest.fixture
def payload():
    return {
        "iss": "https://example.org",
        "aud": "CLIENT_KEY",
        "sub": "111111111",
        "given_name": "test",
        "family_name": "user",
        "email": "test@example.org",
        "iat": int(datetime.now().timestamp()),
        "exp": int((datetime.now() + timedelta(hours=1)).timestamp()),
    }


@pytest.fixture
def exchange_providers(settings):
    settings.JWT_EXCHANGE_PROVIDERS = {
        "example": {"url": "https://example.org/keys", "client_id": "CLIENT_KEY"}
    }


def sign_payload(payload, private_key):
    return jwt.encode(payload, private_key, "RS256")


def jwks(private_key):
    e, n = get_public_numbers(private_key)
    return {
        "alg": "RS256",
        "use": "sig",
        "kty": "RSA",
        "n": encode_int(n),
        "e": encode_int(e),
        "kid": 1,
    }


def encode_int(n: int):
    return base64.b64encode(n.to_bytes(math.ceil(n.bit_length() / 8), "big"))


def set_urlopen_mock(mock, jwks):
    ret = MagicMock()
    ret.getcode.return_value = 200
    ret.read.return_value = json.dumps(jwks)
    ret.__enter__.return_value = ret
    mock.return_value = ret


@patch("jwt.PyJWKClient.get_signing_key_from_jwt")
def test_token_exchange(mock, client, private_key, payload, exchange_providers):
    mock.return_value = jwt.api_jwk.PyJWK(jwks(private_key))
    resp = client.post(
        reverse("apps.auth:token-exchange"),
        content_type="application/json",
        data={"jwt": sign_payload(payload, private_key), "provider": "example"},
    )
    contents = resp.json()
    jwt_service = JWTService()
    atoken = jwt_service.verify_token(contents["atoken"])
    rtoken = jwt_service.verify_token(contents["rtoken"])
    assert atoken["email"] == rtoken["email"] == "test@example.org"
    assert User.objects.filter(email="test@example.org").exists()
