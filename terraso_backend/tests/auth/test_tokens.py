from django.utils import timezone

from apps.auth.oauth2 import Tokens


def test_tokens(access_tokens_google):
    tokens = Tokens.from_google(access_tokens_google)

    assert tokens.access_token
    assert tokens.refresh_token
    assert tokens.expires_at > timezone.now()


def test_tokens_with_openid(access_tokens_google):
    tokens = Tokens.from_google(access_tokens_google)

    open_id = tokens.open_id

    assert open_id
    assert open_id.name == "Testing Terraso"
    assert open_id.given_name == "Testing"
    assert open_id.family_name == "Terraso"
    assert open_id.email == "testingterraso@example.com"
    assert open_id.picture
