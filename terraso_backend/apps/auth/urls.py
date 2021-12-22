from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from apps.auth.views import (
    AppleAuthorizeView,
    AppleCallbackView,
    GoogleAuthorizeView,
    GoogleCallbackView,
)

app_name = "apps.auth"

urlpatterns = [
    path("apple/authorize", csrf_exempt(AppleAuthorizeView.as_view()), name="apple-authorize"),
    path(
        "apple/callback",
        csrf_exempt(AppleCallbackView.as_view()),
        name="apple-callback",
    ),
    path("google/authorize", csrf_exempt(GoogleAuthorizeView.as_view()), name="google-authorize"),
    path(
        "google/callback",
        csrf_exempt(GoogleCallbackView.as_view()),
        name="google-callback",
    ),
]
