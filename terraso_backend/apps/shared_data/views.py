import mimetypes
from dataclasses import asdict

import structlog
from django.http import JsonResponse
from django.views.generic.edit import FormView

from apps.auth.mixins import AuthenticationRequiredMixin
from apps.core.exceptions import ErrorContext, ErrorMessage

from .forms import DataEntryForm

logger = structlog.get_logger(__name__)

mimetypes.init()


class DataEntryFileUploadView(AuthenticationRequiredMixin, FormView):
    def post(self, request, **kwargs):
        form_data = request.POST.copy()
        form_data["created_by"] = str(request.user.id)

        entry_form = DataEntryForm(data=form_data, files=request.FILES)

        if not entry_form.is_valid():
            error_messages = get_error_messages(entry_form.errors.as_data())
            return JsonResponse(
                {"errors": [{"message": [asdict(e) for e in error_messages]}]}, status=400
            )

        data_entry = entry_form.save()

        return JsonResponse(data_entry.to_dict(), status=201)


def get_error_messages(validation_errors):
    error_messages = []

    for field, errors in validation_errors.items():
        for error in errors:
            error_messages.append(
                ErrorMessage(
                    code=error.code,
                    context=ErrorContext(
                        model="DataEntry",
                        field=field,
                        extra=error.message,
                    ),
                )
            )

    return error_messages
