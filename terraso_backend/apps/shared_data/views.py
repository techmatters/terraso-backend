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

import mimetypes
from dataclasses import asdict
from pathlib import Path

import structlog
from config.settings import DATA_ENTRY_ACCEPTED_EXTENSIONS, MEDIA_UPLOAD_MAX_FILE_SIZE
from django.http import JsonResponse
from django.views.generic.edit import FormView

from apps.auth.mixins import AuthenticationRequiredMixin
from apps.core.exceptions import ErrorContext, ErrorMessage
from apps.storage.file_utils import has_multiple_files, is_file_upload_oversized

from .forms import DataEntryForm
from .models import DataEntry

logger = structlog.get_logger(__name__)


mimetypes.init()


class DataEntryFileUploadView(AuthenticationRequiredMixin, FormView):
    def post(self, request, **kwargs):
        form_data = request.POST.copy()
        form_data["created_by"] = str(request.user.id)
        form_data["entry_type"] = DataEntry.ENTRY_TYPE_FILE

        if has_multiple_files(request.FILES.getlist("data_file")):
            error_message = ErrorMessage(
                code="Uploaded more than one file",
                context=ErrorContext(model="DataEntry", field="data_file"),
            )
            return JsonResponse({"errors": [{"message": [asdict(error_message)]}]}, status=400)
        if is_file_upload_oversized(request.FILES.getlist("data_file"), MEDIA_UPLOAD_MAX_FILE_SIZE):
            error_message = ErrorMessage(
                code="File size exceeds 10 MB",
                context=ErrorContext(model="DataEntry", field="data_file"),
            )
            return JsonResponse({"errors": [{"message": [asdict(error_message)]}]}, status=400)
        if not is_valid_shared_data_type(request.FILES.getlist("data_file")):
            error_message = ErrorMessage(
                code="Invalid media type",
                context=ErrorContext(model="Shared Data", field="context_type"),
            )
            return JsonResponse({"errors": [{"message": [asdict(error_message)]}]}, status=400)

        entry_form = DataEntryForm(data=form_data, files=request.FILES)

        if not entry_form.is_valid():
            error_messages = get_error_messages(entry_form.errors.as_data())
            return JsonResponse(
                {"errors": [{"message": [asdict(e) for e in error_messages]}]}, status=400
            )

        data_entry = entry_form.save()

        return JsonResponse(data_entry.to_dict(), status=201)


def is_valid_shared_data_type(files):
    for file in files:
        extension = Path(file.content_type)
        logger.info("EXTENSION")
        type = "." + extension.parts[-1]
        logger.info(type)
        if type not in DATA_ENTRY_ACCEPTED_EXTENSIONS:
            return False
    return True


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
