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
    # Token-based exports (public, no authentication required)
    # HTML landing pages (when format is "html")
    path(
        "token/project/<str:project_token>/<str:project_name>.html",
        csrf_exempt(auth_optional(views.project_export_page)),
        name="project-export-page",
    ),
    path(
        "token/site/<str:site_token>/<str:site_name>.html",
        csrf_exempt(auth_optional(views.site_export_page)),
        name="site-export-page",
    ),
    path(
        "token/user_owned/<str:user_token>/<str:user_name>.html",
        csrf_exempt(auth_optional(views.user_owned_sites_export_page)),
        name="user-owned-sites-export-page",
    ),
    path(
        "token/user_all/<str:user_token>/<str:user_name>.html",
        csrf_exempt(auth_optional(views.user_all_sites_export_page)),
        name="user-all-sites-export-page",
    ),
    # Direct file downloads (CSV/JSON)
    path(
        "token/project/<str:project_token>/<str:project_name>.<str:format>",
        csrf_exempt(auth_optional(views.project_export)),
        name="project-export-by-token",
    ),
    path(
        "token/site/<str:site_token>/<str:site_name>.<str:format>",
        csrf_exempt(auth_optional(views.site_export)),
        name="site-export-by-token",
    ),
    path(
        "token/user_owned/<str:user_token>/<str:user_name>.<str:format>",
        csrf_exempt(auth_optional(views.user_owned_sites_export)),
        name="user-owned-sites-export-by-token",
    ),
    path(
        "token/user_all/<str:user_token>/<str:user_name>.<str:format>",
        csrf_exempt(auth_optional(views.user_all_sites_export)),
        name="user-all-sites-export-by-token",
    ),
    # ID-based exports (authenticated, enforces permissions)
    path(
        "id/project/<str:project_id>/<str:project_name>.<str:format>",
        csrf_exempt(views.project_export_by_id),
        name="project-export-by-id",
    ),
    path(
        "id/site/<str:site_id>/<str:site_name>.<str:format>",
        csrf_exempt(views.site_export_by_id),
        name="site-export-by-id",
    ),
    path(
        "id/user_owned/<str:user_id>/<str:user_name>.<str:format>",
        csrf_exempt(views.user_owned_sites_export_by_id),
        name="user-owned-sites-export-by-id",
    ),
    path(
        "id/user_all/<str:user_id>/<str:user_name>.<str:format>",
        csrf_exempt(views.user_all_sites_export_by_id),
        name="user-all-sites-export-by-id",
    ),
]