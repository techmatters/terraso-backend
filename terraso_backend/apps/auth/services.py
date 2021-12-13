from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Authorization
from .providers import GoogleProvider

User = get_user_model()


class AccountService:
    def sign_up_with_google(self, authorization_code):
        provider = GoogleProvider()
        tokens = provider.fetch_auth_tokens(authorization_code)

        if not tokens.is_valid:
            raise Exception("Error fetching auth tokens: " + tokens.error_description)

        with transaction.atomic():
            user = User.objects.create_user(
                email=tokens.open_id.email,
                first_name=tokens.open_id.given_name,
                last_name=tokens.open_id.family_name,
            )
            Authorization.objects.create(
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                id_token=tokens.id_token,
                expires_at=tokens.expires_at,
                user=user,
                provider=Authorization.PROVIDER_GOOGLE,
            )

        return user
