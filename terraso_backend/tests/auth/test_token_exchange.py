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
    access_token = jwt_service.verify_access_token(contents["atoken"])
    refresh_token = jwt_service.verify_refresh_token(contents["rtoken"])
    assert access_token["email"] == refresh_token["email"] == "test@example.org"
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


def test_token_exchange_is_new_account_true(client, private_key, payload):
    """Test that is_new_account is True when creating a new user"""
    payload["email"] = "newuser@example.org"
    resp = client.post(
        reverse("apps.auth:token-exchange"),
        content_type="application/json",
        data={"jwt": sign_payload(payload, private_key), "provider": "example"},
    )
    contents = resp.json()
    assert contents["is_new_account"] is True
    assert User.objects.filter(email="newuser@example.org").exists()


def test_token_exchange_is_new_account_false(client, private_key, payload):
    """Test that is_new_account is False when user already exists"""
    payload["email"] = "existinguser@example.org"
    # Create user first
    User.objects.create(
        email="existinguser@example.org",
        first_name="test",
        last_name="user",
    )

    resp = client.post(
        reverse("apps.auth:token-exchange"),
        content_type="application/json",
        data={"jwt": sign_payload(payload, private_key), "provider": "example"},
    )
    contents = resp.json()
    assert contents["is_new_account"] is False
    assert User.objects.filter(email="existinguser@example.org").count() == 1


def test_token_exchange_client_supplied_names_new_user(client, private_key, payload):
    """Client-supplied first_name/last_name are used when creating a new user.
    Simulates the mobile Apple Sign In flow: Apple's JWT has no name claims, so
    the mobile app captures fullName from the credential and sends it alongside."""
    # Strip name claims from JWT to mimic Apple's id_token (which never has them)
    payload["email"] = "appleuser@example.org"
    del payload["given_name"]
    del payload["family_name"]

    resp = client.post(
        reverse("apps.auth:token-exchange"),
        content_type="application/json",
        data={
            "jwt": sign_payload(payload, private_key),
            "provider": "example",
            "first_name": "Jane",
            "last_name": "Appleseed",
        },
    )
    contents = resp.json()
    assert contents["is_new_account"] is True
    user = User.objects.get(email="appleuser@example.org")
    assert user.first_name == "Jane"
    assert user.last_name == "Appleseed"


def test_token_exchange_client_supplied_names_backfill_existing(client, private_key, payload):
    """Client-supplied names backfill an existing user whose name fields are empty.
    This is the post-revoke Apple Sign In path: the user already exists but came in
    via a previous Apple sign-in that didn't capture the name."""
    payload["email"] = "nameless@example.org"
    del payload["given_name"]
    del payload["family_name"]
    User.objects.create(email="nameless@example.org", first_name="", last_name="")

    resp = client.post(
        reverse("apps.auth:token-exchange"),
        content_type="application/json",
        data={
            "jwt": sign_payload(payload, private_key),
            "provider": "example",
            "first_name": "Jane",
            "last_name": "Appleseed",
        },
    )
    assert resp.json()["is_new_account"] is False
    user = User.objects.get(email="nameless@example.org")
    assert user.first_name == "Jane"
    assert user.last_name == "Appleseed"


def test_token_exchange_client_supplied_names_do_not_overwrite_existing(
    client, private_key, payload
):
    """Client-supplied names must NOT overwrite a non-empty name on an existing user.
    Users may have edited their name in-app — we never clobber their choice."""
    payload["email"] = "named@example.org"
    del payload["given_name"]
    del payload["family_name"]
    User.objects.create(email="named@example.org", first_name="Existing", last_name="Name")

    resp = client.post(
        reverse("apps.auth:token-exchange"),
        content_type="application/json",
        data={
            "jwt": sign_payload(payload, private_key),
            "provider": "example",
            "first_name": "Should",
            "last_name": "Not Win",
        },
    )
    assert resp.json()["is_new_account"] is False
    user = User.objects.get(email="named@example.org")
    assert user.first_name == "Existing"
    assert user.last_name == "Name"


# ---------------------------------------------------------------------------
# Apple sub-based lookup
#
# These tests cover the sub-aware lookup path that handles the Apple-specific
# failure mode where Apple's id_token sometimes omits the email claim. The
# fixture payload's iss is "https://example.org" by default; tests that need
# to exercise the Apple-specific code path override iss to the literal Apple
# issuer string the production code checks for.
# ---------------------------------------------------------------------------

APPLE_ISS = "https://appleid.apple.com"


def test_token_exchange_apple_sub_lookup_succeeds_with_no_email(client, private_key, payload):
    """When the JWT has no email but the sub matches an existing user's
    apple_sub, the user is found via sub lookup and login succeeds."""
    User.objects.create(
        email="existing@example.org",
        first_name="Existing",
        last_name="User",
        apple_sub="apple-sub-12345",
    )
    payload["iss"] = APPLE_ISS
    payload["sub"] = "apple-sub-12345"
    del payload["email"]
    del payload["given_name"]
    del payload["family_name"]

    resp = client.post(
        reverse("apps.auth:token-exchange"),
        content_type="application/json",
        data={"jwt": sign_payload(payload, private_key), "provider": "example"},
    )
    contents = resp.json()
    assert contents["is_new_account"] is False
    # User row is unchanged — no name overwrite, no email change
    user = User.objects.get(apple_sub="apple-sub-12345")
    assert user.email == "existing@example.org"
    assert user.first_name == "Existing"
    assert user.last_name == "User"


def test_token_exchange_apple_sub_backfilled_on_email_path(client, private_key, payload):
    """When the JWT has both email and sub, and the user is found by email but
    has no apple_sub yet, the sub is backfilled for future sign-ins."""
    User.objects.create(email="backfill@example.org", apple_sub=None)
    payload["iss"] = APPLE_ISS
    payload["sub"] = "apple-sub-backfill"
    payload["email"] = "backfill@example.org"

    resp = client.post(
        reverse("apps.auth:token-exchange"),
        content_type="application/json",
        data={"jwt": sign_payload(payload, private_key), "provider": "example"},
    )
    assert resp.json()["is_new_account"] is False
    user = User.objects.get(email="backfill@example.org")
    assert user.apple_sub == "apple-sub-backfill"


def test_token_exchange_no_email_no_sub_match_returns_400(client, private_key, payload):
    """No email in JWT and no existing user with this sub → clean 400 response.
    Previously this was a 500 + traceback (the old _persist_user ValueError)."""
    payload["iss"] = APPLE_ISS
    payload["sub"] = "apple-sub-orphan"
    del payload["email"]
    del payload["given_name"]
    del payload["family_name"]

    resp = client.post(
        reverse("apps.auth:token-exchange"),
        content_type="application/json",
        data={"jwt": sign_payload(payload, private_key), "provider": "example"},
    )
    assert resp.status_code == 400
    contents = resp.json()
    assert contents["error"] == "missing_email"
    assert "id_token" in contents["detail"]
    # Confirm no user was created
    assert not User.objects.filter(apple_sub="apple-sub-orphan").exists()


def test_token_exchange_apple_sub_collision_login_succeeds(client, private_key, payload):
    """Two users share an Apple ID (rare: e.g. one created with Hide My Email,
    one with Share My Email after revoke + re-auth). The sub already belongs
    to user A; the JWT comes in with email matching user B and the same sub.
    User B is logged in via the email path, the sub backfill on B raises
    IntegrityError, we catch it, and both users remain in their original state.
    """
    user_a = User.objects.create(email="user-a@example.org", apple_sub="shared-apple-sub")
    user_b = User.objects.create(email="user-b@example.org", apple_sub=None)

    payload["iss"] = APPLE_ISS
    payload["sub"] = "shared-apple-sub"
    payload["email"] = "user-b@example.org"

    resp = client.post(
        reverse("apps.auth:token-exchange"),
        content_type="application/json",
        data={"jwt": sign_payload(payload, private_key), "provider": "example"},
    )
    # Login still succeeds — the user in the response is user B, found by email
    contents = resp.json()
    assert "atoken" in contents
    jwt_service = JWTService()
    access_token = jwt_service.verify_access_token(contents["atoken"])
    assert access_token["email"] == "user-b@example.org"

    # Both users still exist with their original apple_sub state
    user_a.refresh_from_db()
    user_b.refresh_from_db()
    assert user_a.apple_sub == "shared-apple-sub"
    assert user_b.apple_sub is None  # backfill was rolled back


def test_token_exchange_apple_sub_collision_logs_sentry_event(client, private_key, payload):
    """The collision case must call sentry_sdk.capture_message so we can
    monitor frequency in Sentry. Logging alone isn't enough — Sentry's default
    LoggingIntegration only captures ERROR and above as events; warnings get
    silently dropped if they don't ride along with an error in the same request.
    """
    User.objects.create(email="primary@example.org", apple_sub="collision-sub")
    User.objects.create(email="duplicate@example.org", apple_sub=None)

    payload["iss"] = APPLE_ISS
    payload["sub"] = "collision-sub"
    payload["email"] = "duplicate@example.org"

    with patch("apps.auth.services.sentry_sdk.capture_message") as mock_capture:
        client.post(
            reverse("apps.auth:token-exchange"),
            content_type="application/json",
            data={"jwt": sign_payload(payload, private_key), "provider": "example"},
        )

    assert mock_capture.call_count == 1
    args, kwargs = mock_capture.call_args
    assert args[0] == "apple_sub_collision"
    assert kwargs["level"] == "warning"
    assert kwargs["extras"]["attempted_sub"] == "collision-sub"
    assert kwargs["extras"]["attempted_user_email"] == "duplicate@example.org"


def test_token_exchange_email_updated_when_found_by_sub(client, private_key, payload):
    """When a user is found via sub-lookup and the JWT carries a different email
    (e.g. the user switched from Hide My Email to Share My Email), the user's
    email is updated to the provider-supplied value. Unlike names, email is
    provider-controlled — we trust the provider's current value."""
    User.objects.create(
        email="relay@privaterelay.appleid.com",
        apple_sub="email-change-sub",
    )
    payload["iss"] = APPLE_ISS
    payload["sub"] = "email-change-sub"
    payload["email"] = "real@example.org"

    resp = client.post(
        reverse("apps.auth:token-exchange"),
        content_type="application/json",
        data={"jwt": sign_payload(payload, private_key), "provider": "example"},
    )
    assert resp.json()["is_new_account"] is False
    user = User.objects.get(apple_sub="email-change-sub")
    assert user.email == "real@example.org"


def test_token_exchange_email_update_blocked_by_existing_user(client, private_key, payload):
    """If the provider sends a new email but another active user already has it,
    the email update is skipped (IntegrityError on unique_active_email). The
    login still succeeds with the old email."""
    User.objects.create(
        email="relay@privaterelay.appleid.com",
        apple_sub="blocked-email-sub",
    )
    User.objects.create(email="taken@example.org")  # another user owns this email

    payload["iss"] = APPLE_ISS
    payload["sub"] = "blocked-email-sub"
    payload["email"] = "taken@example.org"

    resp = client.post(
        reverse("apps.auth:token-exchange"),
        content_type="application/json",
        data={"jwt": sign_payload(payload, private_key), "provider": "example"},
    )
    # Login still succeeds — user found by sub
    assert "atoken" in resp.json()
    # Email was NOT updated (collision with existing user)
    user = User.objects.get(apple_sub="blocked-email-sub")
    assert user.email == "relay@privaterelay.appleid.com"


def test_token_exchange_non_apple_iss_does_not_record_sub(client, private_key, payload):
    """For Google/Microsoft/web sign-ins (non-Apple iss), the apple_sub field
    should never be touched, even though the JWT has a sub claim. The
    apple_sub column is Apple-specific by design."""
    # Default fixture iss is "https://example.org" — explicitly NOT Apple
    payload["email"] = "googleuser@example.org"
    payload["sub"] = "google-sub-9999"

    resp = client.post(
        reverse("apps.auth:token-exchange"),
        content_type="application/json",
        data={"jwt": sign_payload(payload, private_key), "provider": "example"},
    )
    assert resp.json()["is_new_account"] is True
    user = User.objects.get(email="googleuser@example.org")
    assert user.apple_sub is None
