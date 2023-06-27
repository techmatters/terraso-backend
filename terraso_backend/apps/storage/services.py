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

import pathlib
import urllib.request
import uuid

from django.conf import settings
from django.core.files.base import ContentFile

from .s3 import ProfileImageStorage


class UploadService:
    @property
    def storage(self):
        raise NotImplementedError()

    @property
    def base_url(self):
        raise NotImplementedError()

    def upload_url(self, user_id, url):
        file = self._download_from_url(url)
        return self.upload_file(user_id, ContentFile(file))

    def upload_file(self, user_id, file, file_name=None):
        if not file_name:
            file_name = uuid.uuid4().hex

        path = self.get_path_on_storage(user_id, file_name)

        if self.storage.exists(path):
            path = self._uniquify(path)

        self.storage.save(path, file)
        return self.get_uploaded_file_url(path)

    def upload_file_get_path(self, user_id, file, file_name=None):
        if not file_name:
            file_name = uuid.uuid4().hex

        path = self.get_path_on_storage(user_id, file_name)

        if self.storage.exists(path):
            path = self._uniquify(path)

        self.storage.save(path, file)
        return path

    def delete_file(self, path):
        self.storage.delete(path)

    def get_path_on_storage(self, user_id, file_name):
        return f"{user_id}/{file_name}"

    def get_uploaded_file_url(self, path):
        # We want to replace space chars by the encoded %20 value. It's
        # necessary for the result URL be a valid URL to be persisted on
        # URLField, for example. Special characters are ok to be kept.
        clean_filename = path.split("/")[-1].replace(" ", "%20")
        object_name_prefix = "/".join(path.split("/")[:-1])

        return f"{self.base_url}/{object_name_prefix}/{clean_filename}"

    def _download_from_url(self, url):
        with urllib.request.urlopen(url) as file:
            return file.read()

    def _uniquify(self, path):
        path_object = pathlib.Path(path)
        directory = path_object.parent
        file_name = path_object.stem
        file_extension = path_object.suffix

        counter = 1

        given_path = directory.joinpath(f"{file_name}_{counter}{file_extension}")
        while self.storage.exists(str(given_path)):
            counter += 1
            given_path = directory.joinpath(f"{file_name}_{counter}{file_extension}")

        return str(given_path)

    def get_signed_url(self, path):
        signed_url = self.storage.url(path)
        return signed_url

    def get_file(self, path, mode="rb"):
        return self.storage.open(path, mode)


class ProfileImageService(UploadService):
    storage = ProfileImageStorage()
    base_url = settings.PROFILE_IMAGES_BASE_URL

    def get_path_on_storage(self, user_id, file_name):
        return f"{user_id}/profile-image"


profile_image_upload_service = ProfileImageService()
