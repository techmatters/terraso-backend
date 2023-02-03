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

import structlog
from django import forms
from django.core.exceptions import ValidationError

from apps.core.models.landscapes import Landscape

from .services import profile_image_upload_service

logger = structlog.get_logger(__name__)


class LandscapeProfileImageForm(forms.Form):
    data_file = forms.FileField(required=True)
    description = forms.CharField(required=False)
    landscape = forms.ModelChoiceField(
        required=True, to_field_name="slug", queryset=Landscape.objects.all()
    )

    def clean(self):
        data = super().clean()
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
