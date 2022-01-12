from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from apps.storage.views import ProfileImageView

app_name = "apps.storage"

urlpatterns = [path("profile-image", csrf_exempt(ProfileImageView.as_view()), name="profile-image")]
