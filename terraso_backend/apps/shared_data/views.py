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

import rules
import structlog
from config.settings import DATA_ENTRY_ACCEPTED_EXTENSIONS, MEDIA_UPLOAD_MAX_FILE_SIZE
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views import View
from django.views.generic.edit import FormView

from apps.auth.mixins import AuthenticationRequiredMixin
from apps.core.exceptions import ErrorContext, ErrorMessage
from apps.core.models import SharedResource
from apps.storage.file_utils import has_multiple_files, is_file_upload_oversized

from .forms import DataEntryForm
from .models import DataEntry
from .models.data_entries import VALID_TARGET_TYPES

logger = structlog.get_logger(__name__)


mimetypes.init()


class DataEntryFileDownloadView(View):
    def get(self, request, shared_resource_uuid, *args, **kwargs):
        shared_resource = SharedResource.objects.filter(share_uuid=shared_resource_uuid).first()

        if shared_resource is None:
            return HttpResponse("Not Found", status=404)

        not_shared = shared_resource.share_access == SharedResource.SHARE_ACCESS_NO
        needs_authentication = (
            shared_resource.share_access != SharedResource.SHARE_ACCESS_ALL
            and not request.user.is_authenticated
        )

        if not_shared or needs_authentication:
            return HttpResponse("Not Found", status=404)

        source = shared_resource.source

        if not isinstance(source, DataEntry) or source.entry_type != DataEntry.ENTRY_TYPE_FILE:
            # Only support download for data entries files
            return HttpResponse("Not Found", status=404)

        if not rules.test_rule(
            "allowed_to_download_data_entry_file", request.user, shared_resource
        ):
            return HttpResponse("Not Found", status=404)

        signed_url = source.signed_url

        # Redirect to the presigned URL
        return HttpResponseRedirect(signed_url)


class DataEntryFileUploadView(AuthenticationRequiredMixin, FormView):
    @transaction.atomic
    def post(self, request, **kwargs):
        form_data = request.POST.copy()
        form_data["created_by"] = str(request.user.id)
        form_data["entry_type"] = DataEntry.ENTRY_TYPE_FILE
        target_type = form_data.pop("target_type")[0]
        target_slug = form_data.pop("target_slug")[0]
        if target_type not in VALID_TARGET_TYPES:
            logger.error("Invalid target_type provided when adding dataEntry")
            return get_json_response_error(
                [
                    ErrorMessage(
                        code="Invalid target_type provided when adding dataEntry",
                        context=ErrorContext(model="DataEntry", field="target_type"),
                    )
                ]
            )

        content_type = ContentType.objects.get(app_label="core", model=target_type)
        model_class = content_type.model_class()

        try:
            target = model_class.objects.get(slug=target_slug)
        except Exception:
            logger.error(
                "Target not found when adding dataEntry",
                extra={"target_type": target_type, "target_slug": target_slug},
            )
            return get_json_response_error(
                [
                    ErrorMessage(
                        code="Target not found when adding dataEntry",
                        context=ErrorContext(model="DataEntry", field="target_type"),
                    )
                ]
            )

        if has_multiple_files(request.FILES.getlist("data_file")):
            error_message = ErrorMessage(
                code="Uploaded more than one file",
                context=ErrorContext(model="DataEntry", field="data_file"),
            )
            return get_json_response_error([error_message])
        if is_file_upload_oversized(request.FILES.getlist("data_file"), MEDIA_UPLOAD_MAX_FILE_SIZE):
            error_message = ErrorMessage(
                code="File size exceeds 10 MB",
                context=ErrorContext(model="DataEntry", field="data_file"),
            )
            return get_json_response_error([error_message])
        if not is_valid_shared_data_type(request.FILES.getlist("data_file")):
            error_message = ErrorMessage(
                code="invalid_media_type",
                context=ErrorContext(model="Shared Data", field="context_type"),
            )
            return get_json_response_error([error_message])

        entry_form = DataEntryForm(data=form_data, files=request.FILES)

        if not entry_form.is_valid():
            error_messages = get_error_messages(entry_form.errors.as_data())
            return get_json_response_error(error_messages)

        data_entry = entry_form.save()

        data_entry.shared_resources.create(
            target=target,
        )

        return JsonResponse(data_entry.to_dict(), status=201)


def is_valid_shared_data_type(files):
    return all(Path(str(file)).suffix in DATA_ENTRY_ACCEPTED_EXTENSIONS for file in files)


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


def get_json_response_error(error_messages, status=400):
    return JsonResponse(
        {"errors": [{"message": [asdict(e) for e in error_messages]}]}, status=status
    )
