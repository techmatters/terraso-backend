import mimetypes

import structlog
from django.http import JsonResponse
from django.views.generic.edit import FormView

from apps.auth.mixins import AuthenticationRequiredMixin

from .forms import DataEntryForm

logger = structlog.get_logger(__name__)

mimetypes.init()


class DataEntryFileUploadView(AuthenticationRequiredMixin, FormView):
    def post(self, request, **kwargs):
        form_data = request.POST.copy()
        form_data["created_by"] = str(request.user.id)

        entry_form = DataEntryForm(data=form_data, files=request.FILES)

        if not entry_form.is_valid():
            return JsonResponse({"error": dict(entry_form.errors.items())}, status=400)

        data_entry = entry_form.save()

        return JsonResponse(data_entry.to_dict(), status=201)
