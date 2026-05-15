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

from functools import wraps

import structlog
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.http.response import JsonResponse
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from .constants import (
    OAUTH_COOKIE_MAX_AGE_SECONDS,
    OAUTH_COOKIE_NAME,
    SESSION_FLAG_OAUTH_LOGIN,
)
from .services import JWTService

logger = structlog.get_logger(__name__)
User = get_user_model()


class JWTAuthenticationMiddleware:
    def process_view(self, request, view_func, view_args, view_kwargs):
        auth_optional = getattr(view_func, "auth_optional", False)
        auth_required = not auth_optional and not self._is_path_public(request.path)

        # JWT is the source of truth for API endpoints. A Django session cookie
        # (created by the OAuth /authorize flow and retained by clients like
        # iOS CFNetwork) must not be allowed to authenticate API requests.
        # AuthenticationMiddleware ran earlier and may have set request.user
        # from the session; reset it on any non-public path so the JWT layer
        # below is the only acceptable credential.  Paths in PUBLIC_BASE_PATHS
        # (/admin/, /oauth/, /auth/, /healthz/, ...) keep their current
        # session-based behavior because both auth_optional and auth_required
        # are false for them.
        if auth_optional or auth_required:
            request.user = AnonymousUser()

        if request.user.is_authenticated or (not auth_required and not auth_optional):
            return None

        auth_header = request.META.get("HTTP_AUTHORIZATION")
        if not auth_header and auth_optional:
            request.user = AnonymousUser()
            return None

        try:
            request.user = self._get_user_from_jwt(request)
            return None
        except ValidationError as e:
            request.user = AnonymousUser()
            logger.warning("Invalid JWT token", extra={"error": str(e)})
            return JsonResponse({"error": "Unauthorized request"}, status=401)

    def _is_path_public(self, path):
        for public_path in settings.PUBLIC_BASE_PATHS:
            if path.startswith(public_path):
                return True
        return False

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def _get_user_from_jwt(self, request):
        if not request:
            raise ImproperlyConfigured("No request provided")

        auth_header = request.META.get("HTTP_AUTHORIZATION")

        if not auth_header:
            logger.info("Authorization header missing")
            raise ValidationError("Authorization header missing")

        auth_header_parts = auth_header.split()

        if len(auth_header_parts) != 2:
            raise ValidationError(f"Authorization header incorrectly formatted: {auth_header}")

        token_type, token = auth_header_parts

        if token_type != "Bearer":
            raise ValidationError(f"Unexpected token type: {token_type}")

        try:
            decoded_payload = JWTService().verify_access_token(token)
        except ExpiredSignatureError as e:
            # Expected: clients refresh via /auth/tokens and retry.
            logger.info("JWT access token expired")
            raise ValidationError(f"Invalid JWT token: {e}")
        except InvalidTokenError as e:
            logger.exception("Failure to verify JWT token", extra={"token": token})
            raise ValidationError(f"Invalid JWT token: {e}")
        except ValueError as e:
            logger.exception("Not valid JWT token type", extra={"token": token})
            raise ValidationError(f"Invalid JWT token: {e}")

        user = self._get_user(decoded_payload["sub"])

        if not user:
            raise ValidationError("User not found for JWT token")

        return user

    def _get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            logger.error("User from JWT token not found", extra={"user_id": user_id})
            return None


def auth_optional(view_func):
    def wrapped_view(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)

    view_func.auth_optional = True
    return wraps(view_func)(wrapped_view)


class OAuthAuthorizeState:
    def __init__(self, get_response):
        self.get_response = get_response
        self.uri_path = reverse("oauth2_provider:authorize")

    def __call__(self, request):
        response = self.get_response(request)

        if request.path == self.uri_path:
            if request.user.is_anonymous:
                # user accessing OAuth authorize URI and not logged in
                # we store the URL so OAuth can start after login
                cookie = request.get_full_path_info()

                response.set_signed_cookie(
                    OAUTH_COOKIE_NAME,
                    cookie,
                    domain=settings.AUTH_COOKIE_DOMAIN,
                    max_age=OAUTH_COOKIE_MAX_AGE_SECONDS,
                    httponly=True,
                    secure=True,
                    # lax - cookie sent from requests not originating from our domain
                    # need this for the oauth flow b/c request coming from third party
                    samesite="Lax",
                )
            elif request.session.get(SESSION_FLAG_OAUTH_LOGIN) and self._is_grant_redirect(
                response
            ):
                # The OAuth grant has been emitted; the user-agent is leaving
                # the authorize flow with an auth code. The Django session
                # that round-tripped them through /oauth/authorize has no
                # further purpose and would otherwise persist for the
                # default SESSION_COOKIE_AGE (14d). Flush it so the cookie
                # doesn't linger past its reason to exist.
                request.session.flush()

        return response

    @staticmethod
    def _is_grant_redirect(response):
        """A 30x to the OAuth client's redirect_uri carrying a `code` (auth
        code flow) or `id_token` (implicit/hybrid flow) is the signal that
        the grant succeeded. Error redirects use `error=` and are ignored."""
        if response.status_code not in (301, 302):
            return False
        location = response.get("Location", "")
        return "code=" in location or "id_token=" in location
