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

import json
from unittest import mock
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls.base import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture
def upload_url():
    return reverse("shared_data:upload")


@pytest.fixture
def data_entry_payload(request, group, landscape):
    type = request.param
    return dict(
        name="Testing Data File",
        description="This is the description of the testing data file",
        data_file=SimpleUploadedFile(
            name="data_file.json",
            content=json.dumps({"key": "value", "keyN": "valueN"}).encode(),
            content_type="application/json",
        ),
        target_type=type,
        target_slug=group.slug if type == "group" else landscape.slug,
    )


@pytest.mark.parametrize("data_entry_payload", ["group", "landscape"], indirect=True)
@mock.patch("apps.storage.file_utils.get_file_size")
def test_create_oversized_data_entry(mock_get_size, logged_client, upload_url, data_entry_payload):
    mock_get_size.return_value = 50000001
    with patch(
        "apps.shared_data.forms.data_entry_upload_service.upload_file"
    ) as mocked_upload_service:
        mocked_upload_service.return_value = "https://example.org/uploaded_file.json"

        response = logged_client.post(upload_url, data_entry_payload)

        mocked_upload_service.assert_not_called()

    response_data = response.json()
    assert response.status_code == 400
    assert response_data["errors"][0]["message"][0]["code"] == "File size exceeds 10 MB"

    assert "errors" in response_data


@pytest.mark.parametrize("data_entry_payload", ["group", "landscape"], indirect=True)
def test_create_data_entry_successfully(
    logged_client, upload_url, data_entry_payload, landscape, group
):
    with patch(
        "apps.shared_data.forms.data_entry_upload_service.upload_file"
    ) as mocked_upload_service:
        mocked_upload_service.return_value = "https://example.org/uploaded_file.json"

        response = logged_client.post(upload_url, data_entry_payload)
        response_data = response.json()
        assert response.status_code == 201

        mocked_upload_service.assert_called_once()

    assert "id" in response_data
    assert "url" in response_data
    assert response_data["size"]
    assert len(response_data["shared_resources"]) == 1
    if "landscape" == data_entry_payload["target_type"]:
        assert str(landscape.id) in response_data["shared_resources"]
    if "group" == data_entry_payload["target_type"]:
        assert str(group.id) in response_data["shared_resources"]


@pytest.mark.parametrize("data_entry_payload", ["group", "landscape"], indirect=True)
def test_create_data_entry_file_type_different_from_extension(
    logged_client, upload_url, data_entry_payload
):
    data_entry_payload["data_file"] = (
        SimpleUploadedFile(
            name="data_file.pdf",
            content="this is a text file with json extension".encode(),
            content_type="application/pdf",
        ),
    )
    with patch(
        "apps.shared_data.forms.data_entry_upload_service.upload_file"
    ) as mocked_upload_service:
        mocked_upload_service.return_value = "https://example.org/uploaded_file.pdf"

        response = logged_client.post(upload_url, data_entry_payload)

        mocked_upload_service.assert_not_called()

    assert response.status_code == 400

    response_data = response.json()

    assert "errors" in response_data


@pytest.mark.parametrize("data_entry_payload", ["group", "landscape"], indirect=True)
def test_create_data_entry_file_type_csv(logged_client, upload_url, data_entry_payload):
    data_entry_payload["data_file"] = (
        SimpleUploadedFile(
            name="data_file.csv",
            content="col1,col2\nval1,val2".encode(),
            content_type="text/csv",
        ),
    )
    with patch(
        "apps.shared_data.forms.data_entry_upload_service.upload_file"
    ) as mocked_upload_service:
        mocked_upload_service.return_value = "https://example.org/uploaded_file.json"

        response = logged_client.post(upload_url, data_entry_payload)

    assert response.status_code == 201

    response_data = response.json()

    assert "id" in response_data
    assert "url" in response_data
    assert response_data["size"]


@pytest.mark.parametrize("data_entry_payload", ["group", "landscape"], indirect=True)
def test_create_data_entry_file_invalid_type(logged_client, upload_url, data_entry_payload):
    data_entry_payload["data_file"] = (
        SimpleUploadedFile(
            name="data_file.txt",
            content="this is a text file".encode(),
            content_type="text/plain",
        ),
    )
    with patch(
        "apps.shared_data.forms.data_entry_upload_service.upload_file"
    ) as mocked_upload_service:
        mocked_upload_service.return_value = "https://example.org/uploaded_file.json"

        response = logged_client.post(upload_url, data_entry_payload)

        mocked_upload_service.assert_not_called()

    assert response.status_code == 400

    response_data = response.json()

    assert "errors" in response_data


@mock.patch("apps.shared_data.models.data_entries.data_entry_file_storage.url")
def test_download_data_entry_file_shared_all(
    get_url_mock, not_logged_in_client, shared_resource_data_entry_shared_all
):
    redirect_url = "https://example.org/s3_file.json"
    get_url_mock.return_value = redirect_url
    url = reverse(
        "shared_data:download",
        kwargs={"shared_resource_uuid": shared_resource_data_entry_shared_all.share_uuid},
    )
    response = not_logged_in_client.get(url)

    assert response.status_code == 302
    assert response.url == redirect_url


@mock.patch("apps.shared_data.models.data_entries.data_entry_file_storage.url")
def test_download_data_entry_file_shared_members(
    get_url_mock, logged_client, shared_resource_data_entry_shared_members
):
    redirect_url = "https://example.org/s3_file.json"
    get_url_mock.return_value = redirect_url
    url = reverse(
        "shared_data:download",
        kwargs={"shared_resource_uuid": shared_resource_data_entry_shared_members.share_uuid},
    )
    response = logged_client.get(url)

    assert response.status_code == 302
    assert response.url == redirect_url


@mock.patch("apps.shared_data.models.data_entries.data_entry_file_storage.url")
def test_download_data_entry_file_shared_members_fail(
    get_url_mock, logged_client, shared_resource_data_entry_shared_members_user_1
):
    redirect_url = "https://example.org/s3_file.json"
    get_url_mock.return_value = redirect_url
    share_uuid = shared_resource_data_entry_shared_members_user_1.share_uuid
    url = reverse(
        "shared_data:download",
        kwargs={"shared_resource_uuid": share_uuid},
    )
    response = logged_client.get(url)

    assert response.status_code == 404
