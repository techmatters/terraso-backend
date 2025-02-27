# Copyright © 2023 Technology Matters
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


class StoryMapMediaStorage(S3Boto3Storage):
    bucket_name = settings.STORY_MAP_MEDIA_S3_BUCKET


class StoryMapMediaUploadService(UploadService):
    storage = StoryMapMediaStorage(custom_domain=None)
    base_url = settings.STORY_MAP_MEDIA_BASE_URL

    def get_path_on_storage(self, user_id, file_name):
        return f"{user_id}/story-map-media/${file_name}"


story_map_media_upload_service = StoryMapMediaUploadService()
