from datetime import timedelta

from django.utils import timezone

from .openid import OpenID


class Tokens:
    def __init__(
        self,
        access_token="",
        refresh_token="",
        expires_in="",
        id_token="",
        error="",
        error_description="",
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_in = expires_in
        self.id_token = id_token

        self.open_id = OpenID(self.id_token) if self.id_token else None

        self.error = error
        self.error_description = error_description

    @classmethod
    def from_google(cls, google_data):
        return cls(
            access_token=google_data.get("access_token", ""),
            refresh_token=google_data.get("refresh_token"),
            expires_in=google_data.get("expires_in"),
            id_token=google_data.get("id_token"),
            error=google_data.get("error"),
            error_description=google_data.get("error_description"),
        )

    @property
    def expires_at(self):
        return timezone.now() + timedelta(seconds=int(self.expires_in))

    @property
    def is_valid(self):
        return not self.error
