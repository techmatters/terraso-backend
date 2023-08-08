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

from apps.auth.middleware import auth_optional
from apps.core.views import (
    HealthView,
    ParseGeoFileView,
    check_restore_job_status,
    create_restore_job,
)

from .landscapes_views import LandscapeExportView

app_name = "apps.core"

urlpatterns = [
    path("healthz/", HealthView.as_view(), name="healthz"),
    path("admin/restore", create_restore_job),
    path("admin/restore/jobs/<int:task_id>", check_restore_job_status),
    path("gis/parse/", csrf_exempt(ParseGeoFileView.as_view()), name="parse"),
    path(
        "landscapes/<str:slug>/<str:format>",
        csrf_exempt(auth_optional(LandscapeExportView.as_view())),
        name="landscape-export",
    ),
]
