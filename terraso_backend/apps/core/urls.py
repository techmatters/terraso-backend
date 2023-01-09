from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from apps.core.views import (
    HealthView,
    ParseGeoFileView,
    check_restore_job_status,
    create_restore_job,
)

app_name = "apps.core"

urlpatterns = [
    path("healthz/", HealthView.as_view(), name="healthz"),
    path("admin/restore", create_restore_job),
    path("admin/restore/jobs/<int:task_id>", check_restore_job_status),
    path("gis/parse/", csrf_exempt(ParseGeoFileView.as_view()), name="parse"),
]
