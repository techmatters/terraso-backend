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

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("apps.core.urls", namespace="terraso_core")),
    path("admin/", admin.site.urls),
    path("oauth/", include("oauth2_provider.urls", namespace="oauth2_provider")),
    path("auth/", include("apps.auth.urls", namespace="terraso_auth")),
    path("graphql/", include("apps.graphql.urls", namespace="terraso_graphql")),
    path("storage/", include("apps.storage.urls", namespace="terraso_storage")),
    path("shared-data/", include("apps.shared_data.urls", namespace="shared_data")),
]
