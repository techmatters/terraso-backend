from unittest import mock

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse
from moto import mock_s3

pytestmark = pytest.mark.django_db


@mock_s3
@mock.patch("botocore.client.BaseClient._make_api_call")
def test_post_profile_image(mock_s3, client, access_token):
    url = reverse("terraso_storage:profile-image")
    response = client.post(
        url, {"file": ContentFile("test")}, HTTP_AUTHORIZATION=f"Bearer {access_token}"
    )

    mock_s3.assert_called_once()
    assert response.status_code == 200
