from unittest import mock
from unittest.mock import patch

import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from moto import mock_s3

from apps.storage.s3 import ProfileImageStorage

pytestmark = pytest.mark.django_db


@pytest.fixture
def landscape_profile_image_payload(landscape):
    return dict(
        description="This is the description of the testing profile image",
        landscape=landscape.slug,
        data_file=SimpleUploadedFile(
            name="profile_image.jpeg",
            content="test content".encode(),
            content_type="image/jpeg",
        ),
    )


@mock_s3
@mock.patch("botocore.client.BaseClient._make_api_call")
def test_post_user_profile_image(mock_s3, client, access_token):
    url = reverse("terraso_storage:user-profile-image")

    # We need to mock the exists method, otherwise the mocked s3 (moto) will
    # always say the file exists on s3 and it won't be created.
    with mock.patch.object(ProfileImageStorage, "exists", return_value=False):
        response = client.post(
            url, {"file": ContentFile("test")}, HTTP_AUTHORIZATION=f"Bearer {access_token}"
        )

        mock_s3.assert_called_once()
        assert response.status_code == 200


def test_create_data_entry_successfully(logged_client, landscape_profile_image_payload):
    url = reverse("terraso_storage:landscape-profile-image")
    with patch(
        "apps.storage.forms.profile_image_upload_service.upload_file"
    ) as mocked_upload_service:
        mocked_upload_service.return_value = "https://example.org/uploaded_file.jpeg"

        response = logged_client.post(url, landscape_profile_image_payload)

        mocked_upload_service.assert_called_once()

    assert response.status_code == 200

    response_data = response.json()

    assert "message" in response_data
    assert response_data["message"] == "OK"
