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

import json
from unittest import mock
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from mixer.backend.django import mixer

pytestmark = pytest.mark.django_db


def test_add_form_valid(logged_client, users):
    url = reverse("story_map:add")
    data = {
        "title": "Test StoryMap",
        "configuration": json.dumps(
            {
                "title": "Test StoryMap",
                "chapters": [],
            }
        ),
        "publish": "true",
    }
    response = logged_client.post(url, data=data)

    assert response.status_code == 201
    assert response.json()["title"] == data["title"]
    assert response.json()["created_by"] == str(users[0].id)
    assert response.json()["is_published"]


def test_add_form_invalid(logged_client):
    url = reverse("story_map:add")
    data = {"title": "Test StoryMap", "publish": "invalid", "configuration": json.dumps({})}
    response = logged_client.post(url, data=data)

    assert response.status_code == 400
    assert len(response.json()["errors"]) == 1


def test_update_form_valid(logged_client, users):
    story_map = mixer.blend("story_map.StoryMap", created_by=users[0])
    url = reverse("story_map:update")
    data = {
        "id": story_map.pk,
        "title": "Test StoryMap Updated",
        "configuration": json.dumps({"chapters": []}),
        "publish": "false",
    }
    response = logged_client.post(url, data=data)

    assert response.status_code == 201
    assert response.json()["title"] == data["title"]
    assert not response.json()["is_published"]


def test_update_form_invalid(logged_client, users):
    story_map = mixer.blend("story_map.StoryMap", created_by=users[0])
    url = reverse("story_map:update")
    data = {
        "id": story_map.pk,
        "title": "",
        "publish": "invalid",
        "configuration": json.dumps(
            {
                "title": "Test StoryMap",
            }
        ),
    }
    response = logged_client.post(url, data=data)

    assert response.status_code == 400
    assert len(response.json()["errors"]) == 1


def test_update_form_unauthorized(logged_client):
    story_map = mixer.blend("story_map.StoryMap")
    url = reverse("story_map:update")
    data = {
        "id": story_map.pk,
        "title": "Test StoryMap Updated",
        "configuration": json.dumps({"chapters": []}),
        "publish": "false",
    }
    response = logged_client.post(url, data=data)

    assert response.status_code == 400
    assert len(response.json()["errors"]) == 1


def test_update_upload_media(logged_client, users):
    story_map = mixer.blend("story_map.StoryMap", created_by=users[0])
    url = reverse("story_map:update")
    data = {
        "id": story_map.pk,
        "title": "Test StoryMap Updated",
        "publish": "false",
        "files": SimpleUploadedFile(
            name="audio_file.mp3",
            content="content".encode(),
            content_type="audio/mp3",
        ),
        "configuration": json.dumps(
            {
                "title": "Test StoryMap Updated",
                "chapters": [
                    {
                        "id": "chapter-1",
                        "title": "Chapter 1",
                        "description": "Chapter 1 description",
                        "media": {
                            "contentId": "audio_file.mp3",
                            "type": "audio/mp3",
                        },
                    },
                ],
            }
        ),
    }
    with patch(
        "apps.story_map.views.story_map_media_upload_service.upload_file_get_path"
    ) as mocked_upload_service:
        mocked_upload_service.return_value = "https://example.org/uploaded_file.mp3"
        response = logged_client.post(url, data=data)
        mocked_upload_service.assert_called_once()

    json_response = response.json()

    assert response.status_code == 201
    assert json_response["configuration"]["chapters"][0]["media"]["url"] is not None
    assert "contentId" not in json_response["configuration"]["chapters"][0]["media"]


@mock.patch("apps.storage.file_utils.get_file_size")
def test_update_oversized_media_upload(mock_get_size, logged_client, users):
    story_map = mixer.blend("story_map.StoryMap", created_by=users[0])
    url = reverse("story_map:update")
    data = {
        "id": story_map.pk,
        "title": "Test StoryMap Updated",
        "publish": "false",
        "files": SimpleUploadedFile(
            name="audio_file.mp3",
            content="content".encode(),
            content_type="audio/mp3",
        ),
        "configuration": json.dumps(
            {
                "title": "Test StoryMap Updated",
                "chapters": [
                    {
                        "id": "chapter-1",
                        "title": "Chapter 1",
                        "description": "Chapter 1 description",
                        "media": {
                            "contentId": "audio_file.mp3",
                            "type": "audio/mp3",
                        },
                    },
                ],
            }
        ),
    }
    mock_get_size.return_value = 50000001
    with patch(
        "apps.story_map.views.story_map_media_upload_service.upload_file_get_path"
    ) as mocked_upload_service:
        mocked_upload_service.return_value = "https://example.org/uploaded_file.mp3"
        response = logged_client.post(url, data=data)
        mocked_upload_service.assert_not_called()

    json_response = response.json()

    assert response.status_code == 400
    assert json_response["errors"][0]["message"][0]["code"] == "File size exceeds 10 MB"

    assert "errors" in json_response


def test_update_upload_media_invalid(logged_client, users):
    story_map = mixer.blend("story_map.StoryMap", created_by=users[0])
    url = reverse("story_map:update")
    data = {
        "id": story_map.pk,
        "title": "Test StoryMap Invalid Media",
        "publish": "false",
        "files": SimpleUploadedFile(
            name="audio_file.MOV",
            content="content".encode(),
            content_type="movie/MOV",
        ),
        "configuration": json.dumps(
            {
                "title": "Test StoryMap Updated",
                "chapters": [
                    {
                        "id": "chapter-1",
                        "title": "Chapter 1",
                        "description": "Chapter 1 description",
                        "media": {
                            "contentId": "audio_file.MOV",
                            "type": "movie/MOV",
                        },
                    },
                ],
            }
        ),
    }
    with patch(
        "apps.story_map.views.story_map_media_upload_service.upload_file_get_path"
    ) as mocked_upload_service:
        mocked_upload_service.return_value = "https://example.org/uploaded_file.mp3"
        response = logged_client.post(url, data=data)
        mocked_upload_service.assert_not_called()

    response_data = response.json()

    assert response.status_code == 400
    assert response_data["errors"][0]["message"][0]["code"] == "Invalid Media Type"
    assert "errors" in response_data


def test_update_upload_multiple_media_invalid(logged_client, users):
    story_map = mixer.blend("story_map.StoryMap", created_by=users[0])
    url = reverse("story_map:update")
    data = {
        "id": story_map.pk,
        "title": "Test StoryMap Invalid Media",
        "publish": "false",
        "files": [
            SimpleUploadedFile(
                name="audio_file.mp4",
                content="content".encode(),
                content_type="video/mp4",
            ),
            SimpleUploadedFile(
                name="audio_file.MOV",
                content="content".encode(),
                content_type="movie/MOV",
            ),
        ],
        "configuration": json.dumps(
            {
                "title": "Test StoryMap Updated",
                "chapters": [
                    {
                        "id": "chapter-1",
                        "title": "Chapter 1",
                        "description": "Chapter 1 description",
                        "media": {
                            "contentId": "audio_file.mp4",
                            "type": "video/mp4",
                        },
                    },
                    {
                        "id": "chapter-2",
                        "title": "Chapter 2",
                        "description": "Chapter 2 description",
                        "media": {
                            "contentId": "audio_file.MOV",
                            "type": "movie/MOV",
                        },
                    },
                ],
            }
        ),
    }
    with patch(
        "apps.story_map.views.story_map_media_upload_service.upload_file_get_path"
    ) as mocked_upload_service:
        mocked_upload_service.return_value = "https://example.org/uploaded_file.mp3"
        response = logged_client.post(url, data=data)
        mocked_upload_service.assert_not_called()

    response_data = response.json()

    assert response.status_code == 400
    assert response_data["errors"][0]["message"][0]["code"] == "Invalid Media Type"
    assert "errors" in response_data


def test_add_null_media_valid(logged_client, users):
    story_map = mixer.blend("story_map.StoryMap", created_by=users[0])
    url = reverse("story_map:add")
    data = {
        "id": story_map.pk,
        "title": "Test StoryMap Updated",
        "publish": "true",
        "configuration": json.dumps(
            {
                "title": "Test StoryMap Updated",
                "chapters": [
                    {
                        "id": "chapter-1",
                        "title": "Chapter 1",
                        "description": "Chapter 1 description",
                    },
                ],
            }
        ),
    }
    response = logged_client.post(url, data=data)

    assert response.status_code == 201
    assert response.json()["title"] == data["title"]
    assert response.json()["created_by"] == str(users[0].id)
    assert response.json()["is_published"]


def test_add_upload_featured_image(logged_client, users):
    url = reverse("story_map:add")
    data = {
        "title": "Test StoryMap with Featured Image",
        "publish": "false",
        "files": SimpleUploadedFile(
            name="featured_image.jpg",
            content="content".encode(),
            content_type="image/jpeg",
        ),
        "configuration": json.dumps(
            {
                "title": "Test StoryMap with Featured Image",
                "featuredImage": {
                    "contentId": "featured_image.jpg",
                    "type": "image/jpeg",
                    "description": "A beautiful landscape",
                },
                "chapters": [],
            }
        ),
    }
    with patch(
        "apps.story_map.views.story_map_media_upload_service.upload_file_get_path"
    ) as mocked_upload_service:
        mocked_upload_service.return_value = "https://example.org/featured_image.jpg"
        response = logged_client.post(url, data=data)
        mocked_upload_service.assert_called_once()

    json_response = response.json()

    assert response.status_code == 201
    assert json_response["configuration"]["featuredImage"]["url"] is not None
    assert json_response["configuration"]["featuredImage"]["description"] == "A beautiful landscape"
    assert "contentId" not in json_response["configuration"]["featuredImage"]


def test_update_upload_featured_image(logged_client, users):
    story_map = mixer.blend("story_map.StoryMap", created_by=users[0])
    url = reverse("story_map:update")
    data = {
        "id": story_map.pk,
        "title": "Test StoryMap with Featured Image",
        "publish": "false",
        "files": SimpleUploadedFile(
            name="featured_image.png",
            content="content".encode(),
            content_type="image/png",
        ),
        "configuration": json.dumps(
            {
                "title": "Test StoryMap with Featured Image",
                "featuredImage": {
                    "contentId": "featured_image.png",
                    "type": "image/png",
                    "description": "Updated landscape",
                },
                "chapters": [],
            }
        ),
    }
    with (
        patch(
            "apps.story_map.views.story_map_media_upload_service.upload_file_get_path"
        ) as mocked_upload_service,
        patch(
            "apps.story_map.views.story_map_media_upload_service.get_signed_url"
        ) as mocked_get_signed_url,
    ):
        mocked_upload_service.return_value = "https://example.org/featured_image.png"
        mocked_get_signed_url.return_value = "https://example.org/featured_image.png?signed=true"
        response = logged_client.post(url, data=data)
        mocked_upload_service.assert_called_once()
        mocked_get_signed_url.assert_called_once()

    json_response = response.json()

    assert response.status_code == 201
    assert json_response["configuration"]["featuredImage"]["url"] is not None
    assert json_response["configuration"]["featuredImage"]["signedUrl"] is not None
    assert json_response["configuration"]["featuredImage"]["description"] == "Updated landscape"
    assert "contentId" not in json_response["configuration"]["featuredImage"]


def test_update_featured_image_cleanup(logged_client, users):
    """Test that old featured images are deleted when replaced"""
    old_config = {
        "title": "Old Config",
        "featuredImage": {"url": "https://example.org/old_image.jpg", "type": "image/jpeg"},
        "chapters": [],
    }
    story_map = mixer.blend("story_map.StoryMap", created_by=users[0], configuration=old_config)
    url = reverse("story_map:update")
    data = {
        "id": story_map.pk,
        "title": "Updated StoryMap",
        "publish": "false",
        "files": SimpleUploadedFile(
            name="new_image.jpg",
            content="content".encode(),
            content_type="image/jpeg",
        ),
        "configuration": json.dumps(
            {
                "title": "Updated StoryMap",
                "featuredImage": {
                    "contentId": "new_image.jpg",
                    "type": "image/jpeg",
                },
                "chapters": [],
            }
        ),
    }
    with (
        patch(
            "apps.story_map.views.story_map_media_upload_service.upload_file_get_path"
        ) as mocked_upload_service,
        patch(
            "apps.story_map.views.story_map_media_upload_service.delete_file"
        ) as mocked_delete_service,
        patch(
            "apps.story_map.views.story_map_media_upload_service.get_signed_url"
        ) as mocked_get_signed_url,
    ):
        mocked_upload_service.return_value = "https://example.org/new_image.jpg"
        mocked_get_signed_url.return_value = "https://example.org/new_image.jpg?signed=true"
        response = logged_client.post(url, data=data)
        mocked_upload_service.assert_called_once()
        mocked_delete_service.assert_called_once_with("https://example.org/old_image.jpg")

    assert response.status_code == 201
