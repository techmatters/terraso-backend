import mimetypes
import pathlib

import magic
import structlog
from django import forms
from django.core.exceptions import ValidationError

from apps.core.models import Group

from .models import DataEntry
from .services import data_entry_upload_service

mimetypes.init()
logger = structlog.get_logger(__name__)


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
            "data_file",
            "resource_type",
            "size",
            "url",
            "groups",
            "created_by",
        )

    def clean(self):
        cleaned_data = super().clean()

        data_file = cleaned_data["data_file"]

        file_mime_type = magic.from_buffer(data_file.open("rb").read(2048), mime=True)
        allowed_file_extensions = mimetypes.guess_all_extensions(file_mime_type)
        file_extension = pathlib.Path(data_file.name).suffix

        if (
            file_mime_type
            and allowed_file_extensions
            and file_extension not in allowed_file_extensions
        ):
            message = (
                f"Invalid file extension ({file_extension}) for the file type {file_mime_type}"
            )
            logger.info(message)
            raise ValidationError(message, code="invalid")

        cleaned_data["resource_type"] = file_mime_type
        cleaned_data["size"] = data_file.size

        try:
            cleaned_data["url"] = data_entry_upload_service.upload_file(
                str(cleaned_data["created_by"].id),
                cleaned_data["data_file"],
                file_name=data_file.name,
            )
        except Exception:
            error_msg = "Failed to upload the data file"
            logger.exception(error_msg)
            raise ValidationError(error_msg, code="error")

        return cleaned_data
