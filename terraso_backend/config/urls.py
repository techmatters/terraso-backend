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

import oauth2_provider.views as oauth2_views
from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from apps.web_client.sitemap import WebClientSitemap

# OAuth2 provider endpoints
oauth2_endpoint_views = [
    path("authorize/", oauth2_views.AuthorizationView.as_view(), name="authorize"),
    path("token/", oauth2_views.TokenView.as_view(), name="token"),
    path("revoke-token/", oauth2_views.RevokeTokenView.as_view(), name="revoke-token"),
]

if settings.OAUTH2_PROVIDER.get("OIDC_ENABLED", False):
    # OIDC specific views
    oauth2_endpoint_views += [
        path(
            ".well-known/openid-configuration/",
            oauth2_views.ConnectDiscoveryInfoView.as_view(),
            name="openid-configuration",
        ),
        path(".well-known/jwks.json", oauth2_views.JwksInfoView.as_view(), name="jwks-info"),
        path("userinfo/", oauth2_views.UserInfoView.as_view(), name="user-info"),
    ]

if settings.DEBUG:
    # OAuth2 Application Management endpoints
    oauth2_endpoint_views += [
        path("applications/", oauth2_views.ApplicationList.as_view(), name="list"),
        path(
            "applications/register/",
            oauth2_views.ApplicationRegistration.as_view(),
            name="register",
        ),
        path("applications/<pk>/", oauth2_views.ApplicationDetail.as_view(), name="detail"),
        path("applications/<pk>/delete/", oauth2_views.ApplicationDelete.as_view(), name="delete"),
        path("applications/<pk>/update/", oauth2_views.ApplicationUpdate.as_view(), name="update"),
    ]

    # OAuth2 Token Management endpoints
    oauth2_endpoint_views += [
        path(
            "authorized-tokens/",
            oauth2_views.AuthorizedTokensListView.as_view(),
            name="authorized-token-list",
        ),
        path(
            "authorized-tokens/<pk>/delete/",
            oauth2_views.AuthorizedTokenDeleteView.as_view(),
            name="authorized-token-delete",
        ),
    ]

urlpatterns = [
    path("", include("apps.core.urls", namespace="terraso_core")),
    path("admin/", admin.site.urls),
    path(
        "oauth/", include((oauth2_endpoint_views, "oauth2_provider"), namespace="oauth2_provider")
    ),
    path("auth/", include("apps.auth.urls", namespace="terraso_auth")),
    path("graphql/", include("apps.graphql.urls", namespace="terraso_graphql")),
    path("storage/", include("apps.storage.urls", namespace="terraso_storage")),
    path("shared-data/", include("apps.shared_data.urls", namespace="shared_data")),
    path("story-map/", include("apps.story_map.urls", namespace="story_map")),

    # Used for the web client sitemap, not an API call.
    path(
        "sitemap.xml",
        sitemap,
        WebClientSitemap.pathargs(),
        name="django.contrib.sitemaps.views.sitemap",
    ),
]
