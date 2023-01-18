import mimetypes
import pathlib

import magic
import structlog
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from apps.core.models import Group

from .models import DataEntry
from .services import data_entry_upload_service

mimetypes.init()
logger = structlog.get_logger(__name__)

VALID_CSV_TYPES = ["text/plain", "text/csv", "application/csv"]


class DataEntryForm(forms.ModelForm):
    data_file = forms.FileField()
    url = forms.URLField(required=False)
    resource_type = forms.CharField(max_length=255, required=False)
    size = forms.IntegerField(required=False)
    groups = forms.ModelMultipleChoiceField(
        required=True, to_field_name="slug", queryset=Group.objects.all()
    )

    class Meta:
        model = DataEntry
        fields = (
            "name",
            "description",
            "entry_type",
            "data_file",
            "resource_type",
            "size",
            "url",
            "groups",
            "created_by",
        )

    def is_valid_mime_type(self, data_file):
        file_extension = pathlib.Path(data_file.name).suffix
        content_type = data_file.content_type
        file_mime_type = magic.from_buffer(data_file.open("rb").read(2048), mime=True)
        allowed_file_extensions = mimetypes.guess_all_extensions(file_mime_type)

        is_valid = (
            file_mime_type and allowed_file_extensions and file_extension in allowed_file_extensions
        )

        # Also check variations of allowed csv types
        return (
            is_valid
            or (
                file_extension == ".csv"
                and content_type in VALID_CSV_TYPES
                and file_mime_type in VALID_CSV_TYPES
            ),
            f"Invalid file extension ({file_extension}) for the file type {file_mime_type}",
        )

    def clean_data_file(self):
        data_file = self.cleaned_data["data_file"]

        is_valid, message = self.is_valid_mime_type(data_file)
        if not is_valid:
            logger.info(message)
            raise ValidationError(message, code="invalid_extension")

        return data_file

    def clean(self):
        data = self.cleaned_data
        data_file = data.get("data_file")

        if data_file:
            file_extension = pathlib.Path(data_file.name).suffix
            data["resource_type"] = file_extension[1:]
            data["size"] = data_file.size

            try:
                data["url"] = data_entry_upload_service.upload_file(
                    str(data["created_by"].id),
                    data["data_file"],
                    file_name=data_file.name,
                )
            except Exception:
                error_msg = "Failed to upload the data file"
                logger.exception(error_msg)
                raise ValidationError(error_msg, code="error")

        return data
