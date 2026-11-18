# Copyright © 2026 Technology Matters
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

import re
from unittest import mock

import pytest

from apps.storage.services import SoilImageService

pytestmark = pytest.mark.unit


def test_build_object_key_encodes_site_depth_and_name():
    key = SoilImageService().build_object_key(
        site_id="abc123", depth_start=0, depth_end=10, name="main", extension=".jpg"
    )
    assert re.fullmatch(r"soil-images/abc123/0-10/main-[0-9a-f]{32}\.jpg", key)


def test_build_object_key_is_unique_per_call():
    service = SoilImageService()
    first = service.build_object_key(
        site_id="s", depth_start=0, depth_end=10, name="main", extension=".dng"
    )
    second = service.build_object_key(
        site_id="s", depth_start=0, depth_end=10, name="main", extension=".dng"
    )
    assert first != second  # the uuid suffix allows many images per site/depth/name


def test_create_presigned_put_url_binds_bucket_key_and_content_type():
    service = SoilImageService()
    fake_client = mock.Mock()
    fake_client.generate_presigned_url.return_value = "https://silo/signed-put"

    with mock.patch.object(
        type(service.storage), "connection", new_callable=mock.PropertyMock
    ) as connection:
        connection.return_value.meta.client = fake_client
        url = service.create_presigned_put_url(
            "soil-images/s/0-10/abc.jpg", "image/jpeg", expiration=123
        )

    assert url == "https://silo/signed-put"
    args, kwargs = fake_client.generate_presigned_url.call_args
    assert args[0] == "put_object"
    assert kwargs["Params"]["Bucket"] == service.storage.bucket_name
    assert kwargs["Params"]["Key"] == "soil-images/s/0-10/abc.jpg"
    assert kwargs["Params"]["ContentType"] == "image/jpeg"
    assert kwargs["ExpiresIn"] == 123
