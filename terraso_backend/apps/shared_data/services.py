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
from storages.backends.s3boto3 import S3Boto3Storage

from apps.storage.services import UploadService


class DataEntryFileStorage(S3Boto3Storage):
    bucket_name = settings.DATA_ENTRY_FILE_S3_BUCKET


class DataEntryUploadService(UploadService):
    storage = DataEntryFileStorage()
    base_url = settings.DATA_ENTRY_FILE_BASE_URL


data_entry_upload_service = DataEntryUploadService()
