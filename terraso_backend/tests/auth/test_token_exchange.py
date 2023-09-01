import base64
import math
from datetime import datetime, timedelta
from unittest.mock import patch

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


@pytest.fixture(autouse=True)
def exchange_providers(settings):
    settings.JWT_EXCHANGE_PROVIDERS = {
        "example": {"url": "https://example.org/keys", "client_id": "CLIENT_KEY"}
    }


def sign_payload(payload, private_key):
    return jwt.encode(payload, private_key, "RS256")


def get_public_numbers(private_key):
    pubnum = private_key.public_key().public_numbers()
    return pubnum.e, pubnum.n


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
    """JWKS specs expect numbers to be encoded in base64"""
    return base64.b64encode(n.to_bytes(math.ceil(n.bit_length() / 8), "big"))


@pytest.fixture(autouse=True)
def patch_jwks_client(private_key):
    with patch("jwt.PyJWKClient.get_signing_key_from_jwt") as mock:
        mock.return_value = jwt.api_jwk.PyJWK(jwks(private_key))
        yield mock


def test_token_exchange(client, private_key, payload):
    resp = client.post(
        reverse("apps.auth:token-exchange"),
        content_type="application/json",
        data={"jwt": sign_payload(payload, private_key), "provider": "example"},
    )
    contents = resp.json()
    jwt_service = JWTService()
    atoken = jwt_service.verify_access_token(contents["atoken"])
    rtoken = jwt_service.verify_refresh_token(contents["rtoken"])
    assert atoken["email"] == rtoken["email"] == "test@example.org"
    assert User.objects.filter(email="test@example.org").exists()
    user = User.objects.get(email="test@example.org")
    assert user.first_name == payload["given_name"]
    assert user.last_name == payload["family_name"]


def test_token_exchange_token_signed_by_different_key(client, other_private_key, payload):
    """JWKS uses public key for fixture `private_key`, but the token being exchanged
    has been signed by `other_private_key`"""
    resp = client.post(
        reverse("apps.auth:token-exchange"),
        content_type="application/json",
        data={"jwt": sign_payload(payload, other_private_key), "provider": "example"},
    )
    contents = resp.json()
    assert "token_error" in contents
    assert not User.objects.filter(email="test@example.org").exists()


@pytest.mark.parametrize(
    "payload_update",
    [
        {
            "exp": int((datetime.now() - timedelta(seconds=10)).timestamp()),
        },
        {"aud": "BAD_CLIENT"},
    ],
)
def test_token_exchange_bad_id_token(payload_update, client, private_key, payload):
    """Tests that bad id tokens are not verified. The first example is an expired JWT.
    The second has a different client id than the one saved in our config."""
    payload.update(payload_update)
    resp = client.post(
        reverse("apps.auth:token-exchange"),
        content_type="application/json",
        data={"jwt": sign_payload(payload, private_key), "provider": "example"},
    )
    contents = resp.json()
    assert "token_error" in contents
    assert not User.objects.filter(email="test@example.org").exists()
