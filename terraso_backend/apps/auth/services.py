from django.contrib.auth import get_user_model

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
