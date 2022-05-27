from unittest import mock

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse
from moto import mock_s3

from apps.storage.s3 import ProfileImageStorage

pytestmark = pytest.mark.django_db


@mock_s3
@mock.patch("botocore.client.BaseClient._make_api_call")
def test_post_profile_image(mock_s3, client, access_token):
    url = reverse("terraso_storage:profile-image")

    # We need to mock the exists method, otherwise the mocked s3 (moto) will
    # always say the file exists on s3 and it won't be created.
    with mock.patch.object(ProfileImageStorage, "exists", return_value=False):
        response = client.post(
            url, {"file": ContentFile("test")}, HTTP_AUTHORIZATION=f"Bearer {access_token}"
        )

        mock_s3.assert_called_once()
        assert response.status_code == 200
