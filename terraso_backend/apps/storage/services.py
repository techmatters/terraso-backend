import urllib.request

from django.conf import settings
from django.core.files.base import ContentFile

from .s3 import ProfileImageStorage


class ProfileImageService:
    profile_image_storage = ProfileImageStorage()

    def upload_url(self, user_id, url):
        image = self._download_image_from_url(url)
        return self.upload_file(user_id, ContentFile(image))

    def upload_file(self, user_id, image):
        path = self._get_image_path(user_id)
        self.profile_image_storage.save(path, image)
        return self._get_image_url(path)

    def _get_image_path(self, user_id):
        return "{}/profile-image".format(user_id)

    def _get_image_url(self, path):
        return "{}/{}".format(settings.PROFILE_IMAGES_BASE_URL, path)

    def _download_image_from_url(self, url):
        with urllib.request.urlopen(url) as file:
            return file.read()
