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
from graphene_django.utils.testing import graphql_query

from apps.soil_id.graphql.soil_data import image_upload

pytestmark = pytest.mark.django_db

REQUEST_UPLOAD_URL_QUERY = """
    mutation RequestSoilImageUploadUrl($input: SoilImageUploadUrlRequestInput!) {
        requestSoilImageUploadUrl(input: $input) {
            uploadUrl
            objectKey
            errors
        }
    }
"""

FAKE_URL = "https://silo.example/presigned-put"


def _request(client, site_id, content_type="image/jpeg", start=0, end=10):
    return graphql_query(
        REQUEST_UPLOAD_URL_QUERY,
        variables={
            "input": {
                "siteId": str(site_id),
                "depthInterval": {"start": start, "end": end},
                "contentType": content_type,
            }
        },
        client=client,
    )


def test_request_upload_url_returns_presigned_url_and_keyed_object(client, user, site):
    client.force_login(user)  # user owns `site`, so has ENTER_DATA permission
    with mock.patch.object(
        image_upload.soil_image_upload_service,
        "create_presigned_put_url",
        return_value=FAKE_URL,
    ) as mock_put:
        response = _request(client, site.id)

    payload = response.json()["data"]["requestSoilImageUploadUrl"]
    assert payload["errors"] is None
    assert payload["uploadUrl"] == FAKE_URL
    assert re.fullmatch(rf"soil-images/{site.id}/0-10/[0-9a-f]{{32}}\.jpg", payload["objectKey"])
    # the presigned URL is minted for exactly the returned key + content-type
    mock_put.assert_called_once_with(payload["objectKey"], "image/jpeg")


def test_request_upload_url_denied_for_user_without_site_access(client, user_b, site):
    client.force_login(user_b)  # user_b does not own `site`
    with mock.patch.object(
        image_upload.soil_image_upload_service, "create_presigned_put_url"
    ) as mock_put:
        response = _request(client, site.id)

    payload = response.json()["data"]["requestSoilImageUploadUrl"]
    assert payload["uploadUrl"] is None
    assert payload["errors"] is not None
    mock_put.assert_not_called()  # never mint a URL for an unauthorized user


def test_request_upload_url_rejects_unsupported_content_type(client, user, site):
    client.force_login(user)
    with mock.patch.object(
        image_upload.soil_image_upload_service, "create_presigned_put_url"
    ) as mock_put:
        response = _request(client, site.id, content_type="image/png")

    payload = response.json()["data"]["requestSoilImageUploadUrl"]
    assert payload["uploadUrl"] is None
    assert payload["errors"] is not None
    mock_put.assert_not_called()
