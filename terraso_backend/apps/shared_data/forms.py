import mimetypes

import magic
from django import forms
from django.core.exceptions import ValidationError

from .models import DataEntry
from .services import data_entry_upload_service

mimetypes.init()


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

    def save(self, *args, **kwargs):
        return super().save(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()

        data_file = cleaned_data["data_file"]

        file_type = magic.from_buffer(data_file.open("rb").read(2048), mime=True)
        file_type_from_extension = mimetypes.guess_type(data_file.name)[0]

        if file_type != file_type_from_extension:
            raise ValidationError("Invalid file extension for the file type.", code="invalid")

        cleaned_data["resource_type"] = file_type

        try:
            cleaned_data["url"] = data_entry_upload_service.upload_file(
                str(cleaned_data["created_by"].id),
                cleaned_data["data_file"],
                file_name=data_file.name,
            )
        except Exception:
            raise ValidationError("Failed to upload the data file.", code="error")

        return cleaned_data
