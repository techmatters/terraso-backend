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

    def get_path_on_storage(self, user_id, file_name):
        return f"{user_id}/{file_name}"

    def get_uploaded_file_url(self, path):
        return f"{self.base_url}/{path}"

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


class ProfileImageService(UploadService):
    storage = ProfileImageStorage()
    base_url = settings.PROFILE_IMAGES_BASE_URL

    def get_path_on_storage(self, user_id, file_name):
        return f"{user_id}/profile-image"
