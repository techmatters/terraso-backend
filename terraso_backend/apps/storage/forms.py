import mimetypes

import structlog
from django import forms
from django.core.exceptions import ValidationError

from apps.core.models.landscapes import Landscape

from .services import profile_image_upload_service

mimetypes.init()
logger = structlog.get_logger(__name__)


class LandscapeProfileImageForm(forms.Form):
    data_file = forms.FileField(required=True)
    description = forms.CharField(required=False)
    landscape = forms.ModelChoiceField(
        required=True, to_field_name="slug", queryset=Landscape.objects.all()
    )

    def clean(self):
        data = self.cleaned_data
        data_file = data.get("data_file")

        if data_file:
            try:
                data["url"] = profile_image_upload_service.upload_file(
                    data.get("landscape").id,
                    data["data_file"],
                    file_name=data.get("landscape").id,
                )
            except Exception:
                error_msg = "Failed to upload the landscape profile image"
                logger.exception(error_msg)
                raise ValidationError(error_msg, code="error")

        return data
