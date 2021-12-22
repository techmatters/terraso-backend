from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from apps.auth.views import AppleAuthorizeView, GoogleAuthorizeView, GoogleCallbackView

app_name = "apps.auth"

urlpatterns = [
    path("apple/authorize", csrf_exempt(AppleAuthorizeView.as_view()), name="apple-authorize"),
    path("google/authorize", csrf_exempt(GoogleAuthorizeView.as_view()), name="google-authorize"),
    path(
        "google/callback",
        csrf_exempt(GoogleCallbackView.as_view()),
        name="google-callback",
    ),
]
