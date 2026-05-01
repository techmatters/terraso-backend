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

import pytest
from django.contrib.admin.sites import site
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone
from mixer.backend.django import mixer

from apps.core.models import User
from apps.story_map.admin import StoryMapAdmin
from apps.story_map.models import StoryMap

pytestmark = pytest.mark.django_db


def _get_result_pks(response):
    return {story_map.pk for story_map in response.context["cl"].queryset}


def _get_change_form_fields(admin_user, story_map):
    request = RequestFactory().get("/")
    request.user = admin_user

    form_class = StoryMapAdmin(StoryMap, site).get_form(request, story_map)
    return form_class.base_fields


def test_admin_index_does_not_error_for_staff_user(client):
    admin_user = mixer.blend(User, is_staff=True, is_superuser=False)

    client.force_login(admin_user)
    response = client.get(reverse("admin:index"))

    assert response.status_code == 200


def test_story_map_admin_changelist_shows_operational_columns_and_filter(client):
    admin_user = mixer.blend(User, is_staff=True, is_superuser=True)
    owner = mixer.blend(User, email="owner@example.com")
    published_story_map = mixer.blend(
        "story_map.StoryMap",
        title="Published Story Map",
        story_map_id="a4bcc157",
        created_by=owner,
        is_published=True,
        published_at=timezone.now(),
    )
    draft_story_map = mixer.blend(
        "story_map.StoryMap",
        title="Draft Story Map",
        story_map_id="draft001",
        created_by=owner,
        is_published=False,
    )

    client.force_login(admin_user)
    changelist_url = reverse("admin:story_map_storymap_changelist")

    response = client.get(changelist_url)

    assert response.status_code == 200
    assert "Story map name" in response.content.decode()
    assert "Owner" in response.content.decode()
    assert "Is published" in response.content.decode()
    assert "Published at" in response.content.decode()
    assert _get_result_pks(response) == {published_story_map.pk, draft_story_map.pk}

    filtered_response = client.get(changelist_url, {"is_published__exact": "1"})

    assert filtered_response.status_code == 200
    assert _get_result_pks(filtered_response) == {published_story_map.pk}


def test_story_map_admin_search_supports_story_map_fields_and_urls(client):
    admin_user = mixer.blend(User, is_staff=True, is_superuser=True)
    owner = mixer.blend(
        User,
        email="owner@example.com",
        first_name="CourtneyUnique",
        last_name="Owner",
    )
    target_story_map = mixer.blend(
        "story_map.StoryMap",
        title="Territorios indigenas y conflictos sociambientales en America Latina",
        story_map_id="a4bcc157",
        created_by=owner,
    )
    other_story_map = mixer.blend(
        "story_map.StoryMap",
        title="Another Story Map",
        story_map_id="other123",
        created_by=mixer.blend(User, email="other@example.com"),
    )

    client.force_login(admin_user)
    changelist_url = reverse("admin:story_map_storymap_changelist")
    search_terms = [
        target_story_map.title,
        target_story_map.story_map_id,
        target_story_map.slug,
        owner.email,
        owner.first_name,
        f"https://app.terraso.org/tools/story-maps/{target_story_map.story_map_id}/{target_story_map.slug}",
    ]

    for search_term in search_terms:
        response = client.get(changelist_url, {"q": search_term})

        assert response.status_code == 200
        assert _get_result_pks(response) == {target_story_map.pk}
        assert other_story_map.pk not in _get_result_pks(response)


def test_story_map_admin_url_search_respects_current_filters(client):
    admin_user = mixer.blend(User, is_staff=True, is_superuser=True)
    owner = mixer.blend(User, email="owner@example.com")
    published_story_map = mixer.blend(
        "story_map.StoryMap",
        title="Published Story Map",
        story_map_id="published1",
        created_by=owner,
        is_published=True,
    )
    draft_story_map = mixer.blend(
        "story_map.StoryMap",
        title="Draft Story Map",
        story_map_id="draft001",
        created_by=owner,
        is_published=False,
    )

    client.force_login(admin_user)
    changelist_url = reverse("admin:story_map_storymap_changelist")

    published_response = client.get(
        changelist_url,
        {
            "is_published__exact": "1",
            "q": f"https://app.terraso.org/tools/story-maps/{published_story_map.story_map_id}/{published_story_map.slug}",
        },
    )

    assert published_response.status_code == 200
    assert _get_result_pks(published_response) == {published_story_map.pk}

    draft_response = client.get(
        changelist_url,
        {
            "is_published__exact": "1",
            "q": f"https://app.terraso.org/tools/story-maps/{draft_story_map.story_map_id}/{draft_story_map.slug}",
        },
    )

    assert draft_response.status_code == 200
    assert _get_result_pks(draft_response) == set()


def test_story_map_admin_non_superuser_cannot_edit_configuration_fields():
    admin_user = mixer.blend(User, is_staff=True, is_superuser=False)
    story_map = mixer.blend("story_map.StoryMap", created_by=admin_user)

    form_fields = _get_change_form_fields(admin_user, story_map)

    assert "title" in form_fields
    assert "is_published" in form_fields
    assert "featured" in form_fields
    assert "configuration" not in form_fields
    assert "published_configuration" not in form_fields


def test_story_map_admin_superuser_can_edit_configuration_fields():
    admin_user = mixer.blend(User, is_staff=True, is_superuser=True)
    story_map = mixer.blend("story_map.StoryMap")

    form_fields = _get_change_form_fields(admin_user, story_map)

    assert "configuration" in form_fields
    assert "published_configuration" in form_fields


@override_settings(WEB_CLIENT_URL="http://localhost:10000")
def test_story_map_admin_change_form_shows_web_preview_for_published_story_maps(client):
    admin_user = mixer.blend(User, is_staff=True, is_superuser=True)
    owner = mixer.blend(User, email="owner@example.com")
    published_story_map = mixer.blend(
        "story_map.StoryMap",
        title="Test Padding",
        story_map_id="a61aaf9d",
        created_by=owner,
        is_published=True,
    )
    draft_story_map = mixer.blend(
        "story_map.StoryMap",
        title="Draft Story Map",
        story_map_id="draft001",
        created_by=owner,
        is_published=False,
    )

    client.force_login(admin_user)

    published_response = client.get(
        reverse("admin:story_map_storymap_change", args=[published_story_map.pk])
    )
    published_content = published_response.content.decode()

    assert published_response.status_code == 200
    assert "Open published story map" in published_content
    assert (
        f'href="http://localhost:10000/tools/story-maps/{published_story_map.story_map_id}/{published_story_map.slug}"'
        in published_content
    )
    assert (
        f'src="http://localhost:10000/tools/story-maps/{published_story_map.story_map_id}/{published_story_map.slug}/embed"'
        in published_content
    )

    draft_response = client.get(
        reverse("admin:story_map_storymap_change", args=[draft_story_map.pk])
    )
    draft_content = draft_response.content.decode()

    assert draft_response.status_code == 200
    assert "Open published story map" not in draft_content
    assert (
        f"/tools/story-maps/{draft_story_map.story_map_id}/{draft_story_map.slug}/embed"
        not in draft_content
    )


@override_settings(WEB_CLIENT_URL="https://")
def test_story_map_admin_change_form_shows_unavailable_preview_when_web_client_url_missing(client):
    admin_user = mixer.blend(User, is_staff=True, is_superuser=True)
    owner = mixer.blend(User, email="owner@example.com")
    published_story_map = mixer.blend(
        "story_map.StoryMap",
        title="Published Story Map",
        story_map_id="preview01",
        created_by=owner,
        is_published=True,
    )

    client.force_login(admin_user)

    response = client.get(reverse("admin:story_map_storymap_change", args=[published_story_map.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Preview unavailable. Set WEB_CLIENT_* config to enable it." in content
    assert "Open published story map" not in content
    assert (
        f"/tools/story-maps/{published_story_map.story_map_id}/{published_story_map.slug}/embed"
        not in content
    )
