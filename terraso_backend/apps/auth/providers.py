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

import urllib
from datetime import timedelta

import httpx
import jwt
import structlog
from django.conf import settings
from django.utils import timezone

from .oauth2.tokens import Tokens

logger = structlog.get_logger(__name__)


class GoogleProvider:
    GOOGLE_OAUTH_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth?"
    GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
    CLIENT_ID = settings.GOOGLE_CLIENT_ID
    CLIENT_SECRET = settings.GOOGLE_CLIENT_SECRET
    REDIRECT_URI = settings.GOOGLE_AUTH_REDIRECT_URI

    @classmethod
    def login_url(cls, state=None):
        params = {
            "scope": "openid email profile",
            "access_type": "offline",
            "include_granted_scopes": "true",
            "response_type": "code",
            "redirect_uri": cls.REDIRECT_URI,
            "client_id": cls.CLIENT_ID,
        }

        if state:
            params["state"] = state

        return cls.GOOGLE_OAUTH_BASE_URL + urllib.parse.urlencode(params)

    def fetch_auth_tokens(self, authorization_code):
        request_data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "client_id": self.CLIENT_ID,
            "client_secret": self.CLIENT_SECRET,
            "redirect_uri": self.REDIRECT_URI,
        }

        try:
            google_response = httpx.post(self.GOOGLE_TOKEN_URI, data=request_data)
        except httpx.RequestError as exc:
            error_msg = (
                f"Failed to get Google authorization code while requesting {exc.request.url!r}"
            )
            logger.error(error_msg)
            return Tokens.from_google({"error": "request_error", "error_description": error_msg})

        try:
            google_response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            error_msg = (
                f"Error response {exc.response.status_code} while requesting {exc.request.url!r}."
            )
            logger.error(error_msg)
            return Tokens.from_google({"error": "response_error", "error_description": error_msg})

        return Tokens.from_google(google_response.json())


class AppleProvider:
    OAUTH_BASE_URL = "https://appleid.apple.com/auth/authorize?"
    TOKEN_URI = "https://appleid.apple.com/auth/token"
    CLIENT_ID = settings.APPLE_CLIENT_ID
    REDIRECT_URI = settings.APPLE_AUTH_REDIRECT_URI
    JWT_ALGORITHM = "ES256"
    JWT_AUD = "https://appleid.apple.com"

    @classmethod
    def login_url(cls, state=None):
        params = {
            "scope": "name email openid",
            "response_type": "code",
            "response_mode": "form_post",
            "redirect_uri": cls.REDIRECT_URI,
            "client_id": cls.CLIENT_ID,
        }

        if state:
            params["state"] = state

        return cls.OAUTH_BASE_URL + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)

    def fetch_auth_tokens(self, authorization_code):
        request_data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "client_id": self.CLIENT_ID,
            "client_secret": self._build_client_secret(),
            "redirect_uri": self.REDIRECT_URI,
        }

        try:
            apple_response = httpx.post(self.TOKEN_URI, data=request_data)
        except httpx.RequestError as exc:
            error_msg = (
                f"Failed to get Apple authorization code while requesting {exc.request.url!r}"
            )
            logger.error(error_msg)
            return Tokens.from_apple({"error": "request_error", "error_description": error_msg})

        try:
            apple_response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            error_msg = (
                f"Error response {exc.response.status_code} while requesting {exc.request.url!r}."
            )
            logger.error(error_msg)
            return Tokens.from_apple({"error": "response_error", "error_description": error_msg})

        return Tokens.from_apple(apple_response.json())

    def _build_client_secret(self):
        claims = {
            "iss": settings.APPLE_TEAM_ID,
            "aud": self.JWT_AUD,
            "sub": self.CLIENT_ID,
            "iat": timezone.now(),
            "exp": timezone.now() + timedelta(minutes=15),
        }

        jwt_header = {"kid": settings.APPLE_KEY_ID, "alg": self.JWT_ALGORITHM}

        return jwt.encode(
            payload=claims,
            key=settings.APPLE_PRIVATE_KEY.strip(),
            algorithm=self.JWT_ALGORITHM,
            headers=jwt_header,
        )


class MicrosoftProvider:
    OAUTH_BASE_URL = (
        f"https://login.microsoft.com/{settings.MICROSOFT_TENANT}/oauth2/v2.0/authorize?"
    )
    TOKEN_URI = f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT}/oauth2/v2.0/token"
    CLIENT_ID = settings.MICROSOFT_CLIENT_ID
    CLIENT_SECRET = settings.MICROSOFT_CLIENT_SECRET
    REDIRECT_URI = settings.MICROSOFT_AUTH_REDIRECT_URI
    TENANT = settings.MICROSOFT_TENANT

    @classmethod
    def login_url(cls, state=None):
        params = dict(
            client_id=cls.CLIENT_ID,
            response_type="code",
            redirect_uri=cls.REDIRECT_URI,
            scope="email profile openid",
            response_mode="form_post",
        )
        if state:
            params["state"] = state
        return cls.OAUTH_BASE_URL + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)

    @staticmethod
    def _handle_exceptions(exc):
        match type(exc):
            case httpx.RequestError:
                error_msg = f"Failed to get Microsoft token while requesting {exc.request.url!r}"
                error = "request_error"
            case httpx.HTTPStatusError:
                error_msg = (
                    f"Error response {exc.response.status_code} while "
                    f"requesting {exc.request.url!r}."
                )
                error = "response_error"
        return Tokens.from_microsoft(dict(error=error, error_description=error_msg))

    def fetch_auth_tokens(self, authorization_code):
        params = dict(
            client_id=self.CLIENT_ID,
            code=authorization_code,
            grant_type="authorization_code",
            redirect_uri=self.REDIRECT_URI,
            client_secret=self.CLIENT_SECRET,
            # scope="openid email profile",
        )
        try:
            resp = httpx.post(self.TOKEN_URI, data=params)
            resp.raise_for_status()
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            return self._handle_exceptions(exc)
        return Tokens.from_microsoft(resp.json())
