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
        "is_published": "true",
    }
    response = logged_client.post(url, data=data)

    assert response.status_code == 201
    assert response.json()["title"] == data["title"]
    assert response.json()["created_by"] == str(users[0].id)
    assert response.json()["is_published"]


def test_add_form_invalid(logged_client):
    url = reverse("story_map:add")
    data = {"title": "Test StoryMap", "is_published": "invalid", "configuration": json.dumps({})}
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
        "is_published": "false",
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
        "is_published": "invalid",
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
        "is_published": "false",
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
        "is_published": "false",
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
        "is_published": "false",
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
    mock_get_size.return_value = 10000001
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
