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

import structlog
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.http.response import JsonResponse
from jwt.exceptions import InvalidTokenError

from .services import JWTService

logger = structlog.get_logger(__name__)
User = get_user_model()


class JWTAuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user or not request.user.is_authenticated:
            try:
                user = self._get_user_from_jwt(request)
            except ValidationError as e:
                logger.warning("Invalid JWT token", extra={"error": str(e)})
                return JsonResponse({"error": "Unauthorized request"}, status=401)

            if not user:
                logger.warning("No user found for JWT token")
                return JsonResponse({"error": "Unauthorized request"}, status=401)

            if user:
                request.user = user

        response = self.get_response(request)

        return response

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
            decoded_payload = JWTService().verify_token(token)
        except InvalidTokenError as e:
            logger.exception("Failure to verify JWT token", extra={"token": token})
            raise ValidationError(f"Invalid JWT token: {e}")

        return self._get_user(decoded_payload["sub"])

    def _get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            logger.error("User from JWT token not found", extra={"user_id": user_id})
            return None
