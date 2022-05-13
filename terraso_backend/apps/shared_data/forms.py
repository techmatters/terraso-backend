import mimetypes

import magic
import structlog
from django import forms
from django.core.exceptions import ValidationError

from .models import DataEntry
from .services import data_entry_upload_service

mimetypes.init()
logger = structlog.get_logger(__name__)


class DataEntryForm(forms.ModelForm):
    data_file = forms.FileField()
    url = forms.URLField(required=False)
    resource_type = forms.CharField(max_length=255, required=False)

    class Meta:
        model = DataEntry
        fields = (
            "name",
            "description",
            "data_file",
            "resource_type",
            "url",
            "groups",
            "created_by",
        )

    def clean(self):
        cleaned_data = super().clean()

        data_file = cleaned_data["data_file"]

        file_type = magic.from_buffer(data_file.open("rb").read(2048), mime=True)
        file_type_from_extension = mimetypes.guess_type(data_file.name)[0]

        if all(
            (
                file_type,
                file_type_from_extension,
                file_type != file_type_from_extension,
            )
        ):
            message = f"Invalid file extension {file_type_from_extension} for type {file_type}"
            logger.info(message)
            raise ValidationError(message, code="invalid")

        cleaned_data["resource_type"] = file_type

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
