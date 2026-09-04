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

from django.conf import settings

from apps.storage.s3 import ExactKeyWriteStorageMixin, GzipStorageMixin, TerrasoFileStorage
from apps.storage.services import UploadService

GEOJSON_CONTENT_TYPE = "application/geo+json"


class DataEntryFileStorage(TerrasoFileStorage):
    bucket_name = settings.DATA_ENTRY_FILE_S3_BUCKET


class DataEntryUploadService(UploadService):
    storage = DataEntryFileStorage()
    base_url = settings.DATA_ENTRY_FILE_BASE_URL


data_entry_upload_service = DataEntryUploadService()


class GeoJsonFileStorage(GzipStorageMixin, ExactKeyWriteStorageMixin, TerrasoFileStorage):
    bucket_name = settings.DATA_ENTRY_FILE_S3_BUCKET
    querystring_expire = 86400  # 24-hour signed URL expiry

    def _get_write_parameters(self, name, content=None):
        params = super()._get_write_parameters(name, content)
        params["ContentType"] = GEOJSON_CONTENT_TYPE
        return params


class GeoJsonUploadService(UploadService):
    storage = GeoJsonFileStorage()
    base_url = settings.DATA_ENTRY_FILE_BASE_URL

    def get_path_on_storage(self, viz_id, file_name):
        return f"geojson/{viz_id}/{file_name}"


geojson_upload_service = GeoJsonUploadService()
