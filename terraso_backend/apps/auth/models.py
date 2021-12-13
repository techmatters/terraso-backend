from django.conf import settings
from django.db import models


class Authorization(models.Model):
    PROVIDER_APPLE = "apple"
    PROVIDER_GOOGLE = "google"

    PROVIDERS = (
        (PROVIDER_APPLE, "Apple"),
        (PROVIDER_GOOGLE, "Google"),
    )

    access_token = models.TextField()
    refresh_token = models.TextField()
    id_token = models.TextField()
    expires_at = models.DateTimeField(blank=True, null=True)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    provider = models.CharField(max_length=32, choices=PROVIDERS)
