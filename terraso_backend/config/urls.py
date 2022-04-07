from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include("apps.auth.urls", namespace="terraso_auth")),
    path("graphql/", include("apps.graphql.urls", namespace="terraso_graphql")),
    path("storage/", include("apps.storage.urls", namespace="terraso_storage")),
    path("oauth/", include("oauth2_provider.urls", namespace="oauth2_provider")),
]
