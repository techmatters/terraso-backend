from django.urls import path

from apps.core.views import HealthView

app_name = "apps.core"

urlpatterns = [
    path("healthz/", HealthView.as_view(), name="healthz"),
]
