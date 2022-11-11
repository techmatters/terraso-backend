import json
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls.base import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture
def upload_url():
    return reverse("shared_data:upload")


@pytest.fixture
def data_entry_payload(group):
    return dict(
        name="Testing Data File",
        description="This is the description of the testing data file",
        groups=[group.slug],
        data_file=SimpleUploadedFile(
            name="data_file.json",
            content=json.dumps({"key": "value", "keyN": "valueN"}).encode(),
            content_type="application/json",
        ),
    )


def test_create_data_entry_successfully(logged_client, upload_url, data_entry_payload):
    with patch(
        "apps.shared_data.forms.data_entry_upload_service.upload_file"
    ) as mocked_upload_service:
        mocked_upload_service.return_value = "https://example.org/uploaded_file.json"

        response = logged_client.post(upload_url, data_entry_payload)

        mocked_upload_service.assert_called_once()

    assert response.status_code == 201

    response_data = response.json()

    assert "id" in response_data
    assert "url" in response_data
    assert response_data["size"]


def test_create_data_entry_file_type_different_from_extension(
    logged_client, upload_url, data_entry_payload
):
    data_entry_payload["data_file"] = (
        SimpleUploadedFile(
            name="data_file.json",
            content="this is a text file with json extension".encode(),
            content_type="application/json",
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
