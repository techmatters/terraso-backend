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

import threading

import structlog
from django.contrib.auth import get_user_model

from apps.storage.services import ProfileImageService

User = get_user_model()

logger = structlog.get_logger(__name__)


class AsyncTaskHandler:
    def start_task(self, method, args):
        t = threading.Thread(target=method, args=[*args], daemon=True)
        t.start()


def start_update_profile_image_task(user_id, profile_image_url):
    AsyncTaskHandler().start_task(_update_profile_image, [user_id, profile_image_url])


def _update_profile_image(user_id, profile_image_url):
    if not profile_image_url:
        return

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.error("User not found when updating profile image", extra={"user_id": user_id})
        return

    profile_image_service = ProfileImageService()

    try:
        user.profile_image = profile_image_service.upload_url(user_id, profile_image_url)
        user.save()
    except Exception:
        logger.exception("Failed to upload profile image. User ID: {}".format(user_id))
