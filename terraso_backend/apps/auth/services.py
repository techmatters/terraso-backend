# Copyright © 2021-2023 Technology Matters
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

import ipaddress
from contextlib import contextmanager
from datetime import timedelta
from typing import Any, Optional
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import jwt
import structlog
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.core.models import UserPreference
from apps.storage.services import ProfileImageService

from .providers import AppleProvider, GoogleProvider, MicrosoftProvider
from .signals import user_signup_signal

logger = structlog.get_logger(__name__)
User = get_user_model()


class AccountService:
    def sign_up_with_google(self, authorization_code):
        provider = GoogleProvider()
        tokens = provider.fetch_auth_tokens(authorization_code)

        if not tokens.is_valid:
            error_msg = f"Error fetching auth tokens: {tokens.error_description}"
            logger.error(error_msg)
            raise Exception(error_msg)

        return self._persist_user(
            tokens.open_id.email,
            first_name=tokens.open_id.given_name,
            last_name=tokens.open_id.family_name,
            profile_image_url=tokens.open_id.picture,
        )

    def sign_up_with_apple(self, authorization_code, first_name="", last_name=""):
        provider = AppleProvider()
        tokens = provider.fetch_auth_tokens(authorization_code)

        if not tokens.is_valid:
            error_msg = f"Error fetching auth tokens: {tokens.error_description}"
            logger.error(error_msg)
            raise Exception(error_msg)

        return self._persist_user(tokens.open_id.email, first_name=first_name, last_name=last_name)

    def sign_up_with_microsoft(self, authorization_code):
        provider = MicrosoftProvider()
        tokens = provider.fetch_auth_tokens(authorization_code)
        if not tokens.is_valid:
            error_msg = f"Error fetching auth tokens: {tokens.error_description}"
            logger.error(error_msg)
            raise Exception(error_msg)
        return self._persist_user(
            tokens.open_id.email,
            first_name=tokens.open_id.given_name,
            last_name=tokens.open_id.family_name,
            profile_image_url=tokens.open_id.picture,
        )

    def _set_default_preferences(self, user):
        UserPreference.objects.create(user=user, key="notifications", value="true")

    @transaction.atomic
    def _persist_user(self, email, first_name="", last_name="", profile_image_url=None):
        if not email:
            # it is possible for the email not to be set, notably with Microsoft
            # here throw a more descriptive error message
            raise ValueError("Could not create account, user email is empty")
        user, created = User.objects.get_or_create(email=email)

        self._update_profile_image(user, profile_image_url)

        if not created:
            return user, False

        self._set_default_preferences(user)

        update_name = first_name or last_name

        if first_name:
            user.first_name = first_name

        if last_name:
            user.last_name = last_name

        if update_name:
            user.save()

        user_signup_signal.send(sender=self.__class__, user=user)

        return user, True

    def _update_profile_image(self, user, profile_image_url):
        if not profile_image_url:
            return

        profile_image_service = ProfileImageService()
        user_id = str(user.id)

        try:
            user.profile_image = profile_image_service.upload_url(user_id, profile_image_url)
            user.save()
        except Exception:
            logger.exception("Failed to upload profile image. User ID: {}".format(user_id))


class JWTService:
    JWT_SECRET = settings.JWT_SECRET
    JWT_ALGORITHM = settings.JWT_ALGORITHM
    JWT_ACCESS_EXP_DELTA_SECONDS = settings.JWT_ACCESS_EXP_DELTA_SECONDS
    JWT_REFRESH_EXP_DELTA_SECONDS = settings.JWT_REFRESH_EXP_DELTA_SECONDS
    JWT_ISS = settings.JWT_ISS

    def create_token(self, user, expiration=None, extra_payload=None):
        payload = self._get_base_payload(user)
        if expiration:
            payload["exp"] = timezone.now() + timedelta(seconds=expiration)

        complete_payload = {**(extra_payload or {}), **payload}

        return jwt.encode(complete_payload, self.JWT_SECRET, algorithm=self.JWT_ALGORITHM)

    def create_test_access_token(self, user):
        if not user.test_user:
            raise ValueError("User is not a test user")
        return self.create_token(user, None, {"test": True, "access": True})

    def create_access_token(self, user):
        return self.create_token(user, self.JWT_ACCESS_EXP_DELTA_SECONDS, {"access": True})

    def verify_access_token(self, token):
        decoded = self._verify_token(token)
        if not decoded["access"] or not decoded["exp"]:
            raise ValueError("Token is not an access token")
        return decoded

    def create_refresh_token(self, user):
        return self.create_token(user, self.JWT_REFRESH_EXP_DELTA_SECONDS, {"refresh": True})

    def verify_refresh_token(self, token):
        decoded = self._verify_token(token)
        if not decoded["refresh"] or not decoded["exp"]:
            raise ValueError("Token is not a refresh token")
        return decoded

    def create_unsubscribe_token(self, user):
        return self.create_token(user, None, {"unsubscribe": True})

    def verify_unsubscribe_token(self, token):
        decoded = self._verify_token(token)
        if not decoded["unsubscribe"]:
            raise ValueError("Token is not an unsubscribe token")
        return decoded

    def create_story_map_membership_approve_token(self, membership):
        user = membership.user
        return self.create_token(
            user,
            extra_payload={
                "membershipId": str(membership.id),
                "pendingEmail": membership.pending_email if user is None else None,
                "approveStoryMapMembership": True,
            },
        )

    def verify_story_map_membership_approve_token(self, token):
        decoded = self._verify_token(token)
        if not decoded["approveStoryMapMembership"]:
            raise ValueError("Token is not a story map membership approve token")
        return decoded

    def _verify_token(self, token):
        return jwt.decode(token, self.JWT_SECRET, algorithms=self.JWT_ALGORITHM)

    def _get_base_payload(self, user):
        return {
            "iss": self.JWT_ISS,
            "iat": timezone.now(),
            "sub": str(user.id) if user else None,
            "jti": uuid4().hex,
            "email": user.email if user else None,
        }


class PlausibleService:
    """Service for making API calls to plausible service.

    See documentation at https://plausible.io/docs/events-api .
    """

    PLAUSIBLE_URL = settings.PLAUSIBLE_URL
    FRONTEND_URL = settings.WEB_CLIENT_URL
    # fake URL here, because there is no real "signup" URL
    # see Plausible API docs for "url" param
    EVENT_URL = f"{FRONTEND_URL}/signup"

    @staticmethod
    def _prepare_headers(user_agent: str, ip_address: str) -> dict[str, str]:
        return {
            "User-Agent": user_agent,
            "X-Forwarded-For": ip_address,
            "Content-Type": "application/json",
        }

    @classmethod
    def _prepare_body_params(
        cls, event_name: str, event_url: str, referrer: str, props: Optional[dict[str, Any]]
    ):
        return {
            "domain": urlparse(cls.FRONTEND_URL).hostname,
            "name": event_name,
            "url": event_url,
            "referrer": referrer,
            "props": props,
        }

    @staticmethod
    def _get_first_ip_address(string: str):
        addresses = string.split(",")
        for addr in addresses:
            try:
                ip_address = ipaddress.ip_address(addr)
                break
            except ValueError:
                pass
        else:
            # we only get to this branch if we never break
            # i.e. none of the candidates are valid ip addresses
            return None
        return str(ip_address)

    def track_event(
        self,
        event_name: str,
        user_agent: str,
        ip_address: str,
        event_url: str,
        props: Optional[dict[str, Any]] = None,
        referrer: str = "",
    ) -> None:
        """Send a tracking event to Plausible through the HTTP API.
        Throws exception if not succesful."""
        headers = self._prepare_headers(user_agent, ip_address)
        data = self._prepare_body_params(event_name, event_url, referrer, props)
        resp = httpx.post(self.PLAUSIBLE_URL, headers=headers, json=data)

        resp.raise_for_status()

    def track_signup(self, auth_provider: str, req) -> None:
        """Track a successful signup. Include information on which service was used for signup."""
        event_name = "user.signup"
        if "user-agent" not in req.headers:
            logger.error("During signup tracking, request missing header 'user-agent'")
            return
        user_agent = req.headers["user-agent"]
        # here we just assume we are testing locally if 'x-forwarded-for' header is not present
        # this is a mandatory header for the Plausible API, see docs for details
        ip_address = "127.0.0.1"
        if "x-forwarded-for" in req.headers:
            ip_address = self._get_first_ip_address(req.headers["x-forwarded-for"])
            if not ip_address:
                logger.error(
                    "During signup tracking, request header 'x-forwarded-for' was set,"
                    " but no valid ip addresses were found"
                )
                return
        props = {"service": auth_provider}
        self.track_event(event_name, user_agent, ip_address, self.EVENT_URL, props)


class TokenExchangeException(Exception):
    def __init__(self, message: str, error_type: str):
        super().__init__(message)
        self.message = message
        self.error_type = error_type


class TokenExchangeService:
    def __init__(self, token, jwks_uri, client_id, provider_name):
        self.token = token
        self.jwks_uri = jwks_uri
        self.client_id = client_id
        self.provider_name = provider_name

    @classmethod
    def from_payload(cls, payload, settings):
        provider_name = payload["provider"]
        token = payload["jwt"]
        provider = settings.JWT_EXCHANGE_PROVIDERS[provider_name]
        if "url" not in provider or "client_id" not in provider:
            raise TokenExchangeException(
                f"provider {provider_name} is missing config variables", "bad_config"
            )
        return cls(
            token=token,
            jwks_uri=provider["url"],
            client_id=provider["client_id"],
            provider_name=provider_name,
        )

    @staticmethod
    def _get_signing_key(token, provider_url):
        # fetch jwks
        jwks_client = jwt.PyJWKClient(provider_url)
        return jwks_client.get_signing_key_from_jwt(token)

    @staticmethod
    def _verify_payload(token, signing_key, client_id):
        if "alg" not in signing_key._jwk_data:
            raise TokenExchangeException("alg header missing in mobile JWT token")
        algorithms = [signing_key._jwk_data.get("alg", "RS256")]
        return jwt.decode(token, signing_key.key, algorithms=algorithms, audience=client_id)

    @staticmethod
    @contextmanager
    def _transform_error(exception_class, message, error_type):
        try:
            yield
        except exception_class:
            logger.exception(message)
            raise TokenExchangeException(message, error_type=error_type)

    def validate(self):
        with self._transform_error(
            jwt.exceptions.PyJWTError,
            f"could not retrieve signing key for {self.provider_name}",
            "jwks_error",
        ):
            signing_key = self._get_signing_key(self.token, self.jwks_uri)
        with self._transform_error(
            jwt.exceptions.InvalidTokenError, "token was not verified", "token_error"
        ):
            payload = self._verify_payload(self.token, signing_key, self.client_id)

        return payload
