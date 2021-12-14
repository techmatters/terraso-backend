from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from apps.auth.views import GoogleAuthorizeView

app_name = "apps.auth"

urlpatterns = [
    path("google/authorize", csrf_exempt(GoogleAuthorizeView.as_view()), name="google-authorize"),
]
