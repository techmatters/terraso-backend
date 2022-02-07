from datetime import timedelta
from uuid import uuid4

import jwt
import structlog
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.storage.services import ProfileImageService

from .providers import AppleProvider, GoogleProvider

logger = structlog.get_logger(__name__)
User = get_user_model()


class AccountService:
    def sign_up_with_google(self, authorization_code):
        provider = GoogleProvider()
        tokens = provider.fetch_auth_tokens(authorization_code)

        if not tokens.is_valid:
            raise Exception("Error fetching auth tokens: " + tokens.error_description)

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
            raise Exception("Error fetching auth tokens: " + tokens.error_description)

        return self._persist_user(tokens.open_id.email, first_name=first_name, last_name=last_name)

    def _persist_user(self, email, first_name="", last_name="", profile_image_url=None):
        user, created = User.objects.get_or_create(email=email)

        if not created:
            return user

        profile_image_service = ProfileImageService()
        update_name = first_name or last_name

        if first_name:
            user.first_name = first_name

        if last_name:
            user.last_name = last_name

        user_id = str(user.id)
        try:
            if not user.profile_image and profile_image_url:
                user.profile_image = profile_image_service.upload_url(user_id, profile_image_url)
        except Exception:
            logger.exception("Failed to upload profile image. User ID: {}".format(user_id))

        if update_name:
            user.save()

        return user


class JWTService:
    JWT_SECRET = settings.JWT_SECRET
    JWT_ALGORITHM = settings.JWT_ALGORITHM
    JWT_ACCESS_EXP_DELTA_SECONDS = settings.JWT_ACCESS_EXP_DELTA_SECONDS
    JWT_REFRESH_EXP_DELTA_SECONDS = settings.JWT_REFRESH_EXP_DELTA_SECONDS
    JWT_ISS = settings.JWT_ISS

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
            "iss": self.JWT_ISS,
            "iat": timezone.now(),
            "sub": str(user.id),
            "jti": uuid4().hex,
            "email": user.email,
        }
