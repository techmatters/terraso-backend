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


class TerrasoFileStorage(S3Boto3Storage):
    """
    Base for all Terraso S3 storage backends that serve user data.

    Explicitly sets custom_domain=None so signed URLs use the regional
    S3 endpoint instead of inheriting AWS_S3_CUSTOM_DOMAIN (which is
    set globally for the static files CDN and does not serve user data).
    """

    custom_domain = None


class ProfileImageStorage(TerrasoFileStorage):
    bucket_name = settings.PROFILE_IMAGES_S3_BUCKET
