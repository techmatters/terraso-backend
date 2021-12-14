import urllib

import httpx
from django.conf import settings

from .oauth2.tokens import Tokens


class GoogleProvider:
    GOOGLE_OAUTH_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth?"
    GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
    CLIENT_ID = settings.GOOGLE_CLIENT_ID
    CLIENT_SECRET = settings.GOOGLE_CLIENT_SECRET
    REDIRECT_URI = settings.GOOGLE_AUTH_REDIRECT_URI

    @classmethod
    def login_url(self):
        params = {
            "scope": "openid email profile",
            "access_type": "offline",
            "include_granted_scopes": "true",
            "response_type": "code",
            "redirect_uri": self.REDIRECT_URI,
            "client_id": self.CLIENT_ID,
        }

        return self.GOOGLE_OAUTH_BASE_URL + urllib.parse.urlencode(params)

    def fetch_auth_tokens(self, authorization_code):
        request_data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "client_id": self.CLIENT_ID,
            "client_secret": self.CLIENT_SECRET,
            "redirect_uri": self.REDIRECT_URI,
        }
        google_response = httpx.post(self.GOOGLE_TOKEN_URI, data=request_data)

        return Tokens.from_google(google_response.json())
