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
import pathlib

import magic
import structlog
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from apps.core.gis.parsers import is_shape_file_zip
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
            "entry_type",
            "data_file",
            "resource_type",
            "size",
            "url",
            "groups",
            "created_by",
        )

    def validate_file(self, data_file):
        file_extension = pathlib.Path(data_file.name).suffix
        content_type = data_file.content_type
        file_mime_type = magic.from_buffer(data_file.read(2048), mime=True)
        allowed_file_extensions = mimetypes.guess_all_extensions(file_mime_type)

        if file_extension not in settings.DATA_ENTRY_ACCEPTED_EXTENSIONS:
            raise ValidationError(file_extension[1:], code="invalid_extension")

        is_valid = (
            file_mime_type and allowed_file_extensions and file_extension in allowed_file_extensions
        )

        # Document Files
        if file_extension in settings.DATA_ENTRY_DOCUMENT_EXTENSIONS:
            if is_valid:
                return
            else:
                raise ValidationError(file_extension[1:], code="invalid_extension")

        # Spreadsheet Files
        if file_extension in settings.DATA_ENTRY_SPREADSHEET_EXTENSIONS:
            is_valid_csv = (
                file_extension == ".csv"
                and content_type in settings.DATA_ENTRY_VALID_CSV_TYPES
                and file_mime_type in settings.DATA_ENTRY_VALID_CSV_TYPES
            )

            is_valid_spreadsheet = is_valid or is_valid_csv
            if is_valid_spreadsheet:
                return
            else:
                raise ValidationError(file_extension[1:], code="invalid_extension")

        # GIS Files
        if file_extension in settings.DATA_ENTRY_GIS_EXTENSIONS:
            if file_extension == ".kmz" and not file_mime_type == "application/zip":
                raise ValidationError(file_extension[1:], code="invalid_extension")

            if file_extension == ".kml" and not (
                file_mime_type == "text/xml" or file_mime_type == "application/xml"
            ):
                raise ValidationError(file_extension[1:], code="invalid_extension")

            if file_extension == ".gpx" and not (
                file_mime_type == "text/xml" or file_mime_type == "application/xml"
            ):
                raise ValidationError(file_extension[1:], code="invalid_extension")

            if (
                file_extension == ".geojson" or file_extension == ".json"
            ) and file_mime_type not in settings.DATA_ENTRY_VALID_GEOJSON_TYPES:
                raise ValidationError(file_extension[1:], code="invalid_extension")

            if file_extension == ".zip":
                if not is_valid:
                    raise ValidationError(file_extension[1:], code="invalid_zip")
                if not is_shape_file_zip(data_file):
                    raise ValidationError(file_extension[1:], code="invalid_shapefile")

    def clean_data_file(self):
        data_file = self.cleaned_data["data_file"]

        self.validate_file(data_file)

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
