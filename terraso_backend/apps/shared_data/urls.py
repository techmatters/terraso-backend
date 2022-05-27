from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from .views import DataEntryFileUploadView

app_name = "apps.shared_data"

urlpatterns = [
    path("upload/", csrf_exempt(DataEntryFileUploadView.as_view()), name="upload"),
]
