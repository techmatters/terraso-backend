import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from apps.auth.models import User
from apps.auth.service import JWTService


@pytest.fixture
def private_key(scope="session"):
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def other_private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def get_public_numbers(private_key):
    public_key = private_key.public_key()
    return public_key.e, public_key.n


@pytest.fixture
def payload():
    return {
        "iss": "https://example.org",
        "aud": "CLIENT_KEY",
        "sub": "111111111",
        "given_name": "test",
        "family_name": "user",
        "iat": int(datetime.now().timestamp()),
        "exp": int((datetime.now() + timedelta(hours=1)).timestamp()),
    }


def sign_payload(payload, private_key):
    return jwt.encode(payload, private_key, "RS256")


def jwks(private_key):
    e, n = get_public_numbers(private_key)
    return [{"alg": "RS256", "use": "sig", "kty": "RSA", "n": n, "e": e, "kid": 1}]


def set_urlopen_mock(mock, jwks):
    ret = MagicMock()
    ret.getcode.return_value = 200
    ret.read.return_value = json.dumps(jwks)
    ret.__enter__.return_value = ret
    mock.return_value = ret


@patch("urllib.urlopen")
def test_token_exchange(urlopen, client, private_key, payload, settings):
    set_urlopen_mock(urlopen, jwks(private_key))
    with settings(
        JWT_EXCHANGE_PROVIDERS={
            "example": {"url": "https://example.org/keys", "client_id": "CLIENT_KEY"}
        }
    ):
        resp = client.post(
            "/auth/token-exchange",
            data={"jwt": sign_payload(payload, private_key), "provider": "example"},
        )
    contents = json(resp.contents)
    jwt_service = JWTService()
    atoken = jwt_service.decode(contents["atoken"])
    rtoken = jwt_service.decode(contents["rtoken"])
    assert atoken["email"] == rtoken["email"] == "test@example.org"
    assert User.objects.filter(email="test@example.org").exists()
