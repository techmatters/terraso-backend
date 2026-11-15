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
from django.utils import timezone
from graphene_django.utils.testing import graphql_query
from mixer.backend.django import mixer

from apps.collaboration.models import Membership, MembershipList
from apps.story_map.collaboration_roles import ROLE_EDITOR

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("operation", ["add", "update"])
@pytest.mark.parametrize("media_field", ["media", "mediaItems"])
def test_save_and_read_chapter_uploads(operation, media_field, logged_client, users):
    items = [
        {
            "id": f"image-{index}",
            "contentId": f"upload-{index}",
            "type": "image/jpeg",
            "filename": f"photo-{index}.jpg",
            "altText": f"Photo {index}",
            "crop": {"position": {"x": 0.5, "y": 0.5}, "scale": 1},
        }
        for index in range(1 if media_field == "media" else 2)
    ]
    embedded = {"id": "embedded-1", "type": "embedded", "source": "youtube", "url": "embed"}
    chapter = {
        "id": "chapter-1",
        "mediaPresentation": "gallery",
        media_field: items[0] if media_field == "media" else [*items, embedded],
    }
    data = {
        "title": "Uploaded Story",
        "publish": "true",
        "configuration": json.dumps({"chapters": [chapter]}),
        "files": [
            SimpleUploadedFile(item["contentId"], b"image", content_type="image/jpeg")
            for item in items
        ],
    }
    if operation == "update":
        story = mixer.blend("story_map.StoryMap", created_by=users[0], configuration={})
        data["id"] = story.pk
    expected_items = [
        {
            **{key: value for key, value in item.items() if key != "contentId"},
            "url": f"stored/{item['id']}",
            "signedUrl": f"stored/{item['id']}?signed=save",
        }
        for item in items
    ]
    expected = {
        **chapter,
        media_field: expected_items[0] if media_field == "media" else [*expected_items, embedded],
    }
    with (
        patch("apps.story_map.views.story_map_media_upload_service.upload_file_get_path") as upload,
        patch("apps.story_map.views.story_map_media_upload_service.get_signed_url") as sign,
    ):
        upload.side_effect = [item["url"] for item in expected_items]
        sign.side_effect = lambda path: f"{path}?signed=save"
        response = logged_client.post(reverse(f"story_map:{operation}"), data=data)
        assert response.status_code == 201
        assert response.json()["configuration"]["chapters"] == [expected]
        assert upload.call_count == len(items)

        sign.side_effect = lambda path: f"{path}?signed=read"
        read = graphql_query(
            """query($id: ID!) {
              storyMap(id: $id) { configuration publishedConfiguration }
            }""",
            variables={"id": response.json()["id"]},
            client=logged_client,
        ).json()
    assert "errors" not in read
    for field in ("configuration", "publishedConfiguration"):
        result = json.loads(read["data"]["storyMap"][field])["chapters"][0]
        for item in expected_items:
            item["signedUrl"] = item["url"] + "?signed=read"
        assert result == expected


@pytest.mark.parametrize("operation", ["add", "update"])
@pytest.mark.parametrize(
    "chapter",
    [
        {"mediaItems": None},
        {"mediaItems": {}},
        {"mediaItems": "invalid"},
        {"mediaItems": [None]},
        {"mediaItems": [[]]},
        {"mediaItems": [{}]},
        {"mediaItems": [{"type": None}]},
        {"mediaItems": [{"type": 1}]},
        {"mediaItems": [{"type": "image"}, {"type": "movie/MOV"}]},
        {"media": []},
        {"media": {"type": "invalid"}},
    ],
)
def test_save_rejects_invalid_chapter_media(operation, chapter, logged_client, users):
    data = {
        "title": "Invalid Story",
        "publish": "false",
        "configuration": json.dumps({"chapters": [{"media": {"type": "image"}, **chapter}]}),
    }
    if operation == "update":
        data["id"] = mixer.blend("story_map.StoryMap", created_by=users[0]).pk
    response = logged_client.post(reverse(f"story_map:{operation}"), data=data)
    assert response.status_code == 400
    assert response.json()["errors"][0]["message"][0]["code"] == "Invalid Media Type"


@pytest.mark.parametrize("change", ["reorder", "remove", "empty"])
def test_update_chapter_media_cleanup(change, logged_client, users):
    retained = {"type": "image/jpeg", "url": "retained"}
    published = {"type": "audio/mp3", "url": "published"}
    removed = {"type": "video/mp4", "url": "removed"}
    embedded = {"type": "embedded", "url": "embed"}
    story = mixer.blend(
        "story_map.StoryMap",
        created_by=users[0],
        is_published=True,
        configuration={"chapters": [{"mediaItems": [retained, published, removed, embedded]}]},
        published_configuration={"chapters": [{"media": published}]},
    )
    items = [embedded, removed, published, retained] if change == "reorder" else [retained]
    chapter = {"mediaItems": [] if change == "empty" else items, "mediaPresentation": "carousel"}
    if change == "empty":
        chapter["media"] = {"type": "invalid", "contentId": "ignored", "url": "ignored"}
    config = {"chapters": [chapter, {"media": retained}]}
    with (
        patch("apps.story_map.views.story_map_media_upload_service.delete_file") as delete,
        patch("apps.story_map.views.story_map_media_upload_service.get_signed_url") as sign,
        patch("apps.story_map.views.story_map_media_upload_service.upload_file_get_path") as upload,
    ):
        sign.side_effect = lambda path: path + "?signed"
        response = logged_client.post(
            reverse("story_map:update"),
            data={
                "id": story.pk,
                "title": "Cleanup Story",
                "publish": "false",
                "configuration": json.dumps(config),
            },
        )
        assert response.status_code == 201
        if change == "reorder":
            delete.assert_not_called()
        else:
            delete.assert_called_once_with("removed")
        upload.assert_not_called()
        read = graphql_query(
            "query($id: ID!) { storyMap(id: $id) { configuration } }",
            variables={"id": str(story.pk)},
            client=logged_client,
        ).json()
    assert "errors" not in read
    result = json.loads(read["data"]["storyMap"]["configuration"])["chapters"][0]
    assert result["mediaPresentation"] == "carousel"
    assert [item["url"] for item in result["mediaItems"]] == [
        item["url"] for item in chapter["mediaItems"]
    ]
    if change == "empty":
        assert result == chapter


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


@pytest.mark.parametrize("as_editor", [False, True])
def test_unpublish_preserves_draft_and_published_snapshot(logged_client, users, as_editor):
    membership_list = mixer.blend(MembershipList)
    if as_editor:
        mixer.blend(
            Membership,
            membership_list=membership_list,
            user=users[0],
            user_role=ROLE_EDITOR,
            membership_status=Membership.APPROVED,
        )
    draft = {"title": "Latest draft", "chapters": []}
    published = {"title": "Public version", "chapters": []}
    story_map = mixer.blend(
        "story_map.StoryMap",
        created_by=users[1] if as_editor else users[0],
        membership_list=membership_list,
        configuration=draft,
        published_configuration=published,
        is_published=True,
        published_at=timezone.now(),
    )
    identity = (story_map.title, story_map.slug, story_map.story_map_id)
    data = {"id": story_map.pk, "unpublish": "true"}

    for _ in range(2):
        response = logged_client.post(reverse("story_map:update"), data=data)
        assert response.status_code == 201
        assert response.json()["is_published"] is False
        assert response.json()["published_at"] is None

    story_map.refresh_from_db()
    assert story_map.configuration == draft
    assert story_map.published_configuration == published
    assert (story_map.title, story_map.slug, story_map.story_map_id) == identity
    assert story_map.membership_list == membership_list
    assert story_map.published_at is None

    response = logged_client.post(
        reverse("story_map:update"),
        data={
            "id": story_map.pk,
            "title": story_map.title,
            "configuration": json.dumps(draft),
            "publish": "true",
        },
    )
    assert response.status_code == 201
    story_map.refresh_from_db()
    assert story_map.is_published
    assert story_map.published_at is not None
    assert story_map.published_configuration == draft
    assert (story_map.slug, story_map.story_map_id) == identity[1:]


@pytest.mark.parametrize("membership_status", [Membership.PENDING, None])
def test_unpublish_requires_owner_or_approved_editor(logged_client, users, membership_status):
    membership_list = mixer.blend(MembershipList)
    if membership_status:
        mixer.blend(
            Membership,
            membership_list=membership_list,
            user=users[0],
            user_role=ROLE_EDITOR,
            membership_status=membership_status,
        )
    story_map = mixer.blend(
        "story_map.StoryMap",
        created_by=users[1],
        membership_list=membership_list,
        is_published=True,
    )
    response = logged_client.post(
        reverse("story_map:update"), data={"id": story_map.pk, "unpublish": "true"}
    )
    assert response.status_code == 400
    assert response.json()["errors"]
    story_map.refresh_from_db()
    assert story_map.is_published


def test_unpublish_rejects_simultaneous_publish(logged_client, users):
    story_map = mixer.blend("story_map.StoryMap", created_by=users[0], is_published=True)
    response = logged_client.post(
        reverse("story_map:update"),
        data={"id": story_map.pk, "publish": "true", "unpublish": "true"},
    )
    assert response.status_code == 400
    assert response.json()["errors"]
    story_map.refresh_from_db()
    assert story_map.is_published


def test_draft_save_does_not_change_publication_or_restore_concurrent_unpublish(
    logged_client, users
):
    published = {"title": "Public version", "chapters": []}
    published_at = timezone.now()
    story_map = mixer.blend(
        "story_map.StoryMap",
        created_by=users[0],
        configuration=published,
        published_configuration=published,
        is_published=True,
        published_at=published_at,
    )
    draft = {"title": "New draft", "chapters": []}
    data = {
        "id": story_map.pk,
        "title": story_map.title,
        "configuration": json.dumps(draft),
        "publish": "false",
    }
    assert logged_client.post(reverse("story_map:update"), data=data).status_code == 201
    story_map.refresh_from_db()
    assert story_map.is_published
    assert story_map.published_at == published_at
    assert story_map.published_configuration == published

    def unpublish_during_save(config, instance, request):
        response = logged_client.post(
            reverse("story_map:update"), data={"id": story_map.pk, "unpublish": "true"}
        )
        assert response.status_code == 201
        return config

    with patch("apps.story_map.views.handle_config_media", side_effect=unpublish_during_save):
        assert logged_client.post(reverse("story_map:update"), data=data).status_code == 201
    story_map.refresh_from_db()
    assert story_map.configuration == draft
    assert story_map.published_configuration == published
    assert not story_map.is_published
    assert story_map.published_at is None


def test_update_upload_media(logged_client, users):
    story_map = mixer.blend("story_map.StoryMap", created_by=users[0])
    url = reverse("story_map:update")
    data = {
        "id": story_map.pk,
        "title": "Test StoryMap Updated",
        "publish": "false",
        "files": SimpleUploadedFile(
            name="audio_file.mp3",
            content=b"content",
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
            content=b"content",
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
            content=b"content",
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
                content=b"content",
                content_type="video/mp4",
            ),
            SimpleUploadedFile(
                name="audio_file.MOV",
                content=b"content",
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
            content=b"content",
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
            content=b"content",
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
            content=b"content",
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
