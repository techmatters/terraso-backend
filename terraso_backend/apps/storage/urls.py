from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from apps.storage.views import LandscapeProfileImageView, UserProfileImageView

app_name = "apps.storage"

urlpatterns = [
    path(
        "user-profile-image", csrf_exempt(UserProfileImageView.as_view()), name="user-profile-image"
    ),
    path(
        "landscape-profile-image",
        csrf_exempt(LandscapeProfileImageView.as_view()),
        name="landscape-profile-image",
    ),
]
