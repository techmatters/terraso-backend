from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("graphql/", include("apps.graphql.urls", namespace="terraso_graphql")),
    path("auth/", include("apps.auth.urls", namespace="terraso_auth")),
    path("storage/", include("apps.storage.urls", namespace="terraso_storage")),
]
