# Copyright © 2021-2025 Technology Matters
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

from apps.auth.middleware import auth_optional

from . import views

app_name = "apps.export"

urlpatterns = [
    path(
        "project/<str:project_token>/<str:project_name>.<str:format>",
        csrf_exempt(auth_optional(views.project_export)),
        name="project-export",
    ),
    path(
        "site/<str:site_token>/<str:site_name>.<str:format>",
        csrf_exempt(auth_optional(views.site_export)),
        name="site-export",
    ),
    path(
        "user_owned/<str:user_token>/<str:user_name>.<str:format>",
        csrf_exempt(auth_optional(views.user_owned_sites_export)),
        name="user-owned-sites-export",
    ),
    path(
        "user_all/<str:user_token>/<str:user_name>.<str:format>",
        csrf_exempt(auth_optional(views.user_all_sites_export)),
        name="user-all-sites-export",
    ),
]