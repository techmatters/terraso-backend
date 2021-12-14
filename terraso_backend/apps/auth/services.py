from datetime import timedelta
from uuid import uuid4

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from .providers import AppleProvider, GoogleProvider

User = get_user_model()


class AccountService:
    def sign_up_with_google(self, authorization_code):
        provider = GoogleProvider()
        tokens = provider.fetch_auth_tokens(authorization_code)

        if not tokens.is_valid:
            raise Exception("Error fetching auth tokens: " + tokens.error_description)

        user, _ = User.objects.update_or_create(
            email=tokens.open_id.email,
            defaults={
                "first_name": tokens.open_id.given_name,
                "last_name": tokens.open_id.family_name,
            },
        )

        return user

    def sign_up_with_apple(self, authorization_code, first_name="", last_name=""):
        provider = AppleProvider()
        tokens = provider.fetch_auth_tokens(authorization_code)

        if not tokens.is_valid:
            raise Exception("Error fetching auth tokens: " + tokens.error_description)

        user, _ = User.objects.update_or_create(
            email=tokens.open_id.email,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
            },
        )

        return user


class JWTService:
    JWT_SECRET = settings.JWT_SECRET
    JWT_ALGORITHM = settings.JWT_ALGORITHM
    JWT_ACCESS_EXP_DELTA_SECONDS = settings.JWT_ACCESS_EXP_DELTA_SECONDS
    JWT_REFRESH_EXP_DELTA_SECONDS = settings.JWT_REFRESH_EXP_DELTA_SECONDS

    def create_access_token(self, user):
        payload = self._get_base_payload(user)
        payload["exp"] = timezone.now() + timedelta(seconds=self.JWT_ACCESS_EXP_DELTA_SECONDS)

        return jwt.encode(payload, self.JWT_SECRET, algorithm=self.JWT_ALGORITHM)

    def create_refresh_token(self, user):
        payload = self._get_base_payload(user)
        payload["exp"] = timezone.now() + timedelta(seconds=self.JWT_REFRESH_EXP_DELTA_SECONDS)

        return jwt.encode(payload, self.JWT_SECRET, algorithm=self.JWT_ALGORITHM)

    def verify_token(self, token):
        return jwt.decode(token, self.JWT_SECRET, algorithms=self.JWT_ALGORITHM)

    def _get_base_payload(self, user):
        return {
            "iss": "https://terraso.org",
            "iat": timezone.now(),
            "sub": str(user.id),
            "jti": uuid4().hex,
            "email": user.email,
        }
