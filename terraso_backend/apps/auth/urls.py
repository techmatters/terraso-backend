# Copyright © 2021-2023 Technology Matters
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see https://www.gnu.org/licenses/.

from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from apps.auth.views import (
    AppleAuthorizeView,
    AppleCallbackView,
    GoogleAuthorizeView,
    GoogleCallbackView,
    LogoutView,
    RefreshAccessTokenView,
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
    path("tokens", csrf_exempt(RefreshAccessTokenView.as_view()), name="tokens"),
    path("logout", csrf_exempt(LogoutView.as_view()), name="logout"),
]
