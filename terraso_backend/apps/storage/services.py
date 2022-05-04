import urllib.request

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

    def upload_file(self, user_id, file):
        path = self.get_path_on_storage(user_id)
        self.storage.save(path, file)
        return self.get_uploaded_file_url(path)

    def get_path_on_storage(self, user_id):
        return f"{user_id}/"

    def get_uploaded_file_url(self, path):
        return "{}/{}".format(self.base_url, path)

    def _download_from_url(self, url):
        with urllib.request.urlopen(url) as file:
            return file.read()


class ProfileImageService(UploadService):
    storage = ProfileImageStorage()
    base_url = settings.PROFILE_IMAGES_BASE_URL

    def get_path_on_storage(self, user_id):
        return "{}/profile-image".format(user_id)
