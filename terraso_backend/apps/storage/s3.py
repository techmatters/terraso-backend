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

import gzip

from django.conf import settings
from django.core.files.base import ContentFile
from storages.backends.s3boto3 import S3Boto3Storage

# gzip level for compressed objects, pinned below gzip's default of 9
# as levels beyond 6 can start taking seconds of CPU time for very
# little compression gains
GZIP_COMPRESS_LEVEL = 6


class TerrasoFileStorage(S3Boto3Storage):
    """
    Base for all Terraso S3 storage backends that serve user data.

    Explicitly sets custom_domain=None so signed URLs use the regional
    S3 endpoint instead of inheriting AWS_S3_CUSTOM_DOMAIN (which is
    set globally for the static files CDN and does not serve user data).
    """

    custom_domain = None


class GzipStorageMixin:
    """Gzip-compresses every object the storage writes."""

    def _gzip_content(self, content):
        if content.seekable():
            content.seek(0)
        # mtime=0 keeps the output deterministic: identical input produces
        # identical bytes (good for caching).
        return ContentFile(
            gzip.compress(content.read(), compresslevel=GZIP_COMPRESS_LEVEL, mtime=0)
        )

    def _save(self, name, content):
        return super()._save(name, self._gzip_content(content))

    def _get_write_parameters(self, name, content=None):
        params = super()._get_write_parameters(name, content)
        params["ContentEncoding"] = "gzip"
        return params


class ExactKeyWriteStorageMixin:
    """Adds ``overwrite()``, a write that keeps the exact key it was given.

    TEMPORARY CODE: its only caller is the ``compress_existing_geojson``
    backfill command, which runs once per bucket. Delete this mixin together
    with that command once the backfill has run in production -- nothing else
    here is expected to outlive it.
    """

    def overwrite(self, name, content):
        """Write ``content`` to exactly ``name``, even if that key already exists."""
        return self._save(name, content)


class ProfileImageStorage(TerrasoFileStorage):
    bucket_name = settings.PROFILE_IMAGES_S3_BUCKET
