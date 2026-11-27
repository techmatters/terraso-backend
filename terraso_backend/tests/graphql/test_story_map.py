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

import pytest
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse
from mixer.backend.django import mixer

from apps.collaboration.models import Membership, MembershipList
from apps.story_map.models import StoryMap

pytestmark = pytest.mark.django_db


def test_unpublished_map_is_hidden_from_visitors_but_remains_editable(
    logged_client, client_query, client_query_no_token, users
):
    story_map = mixer.blend(
        StoryMap,
        created_by=users[0],
        configuration={"title": "Draft", "chapters": []},
        published_configuration={"title": "Published", "chapters": []},
        is_published=True,
        featured=True,
        membership_list=None,
    )
    query = """
        query MapAccess($storyMapId: String!) {
          storyMaps(storyMapId: $storyMapId) {
            edges { node { id configuration publishedConfiguration isPublished } }
          }
          featuredStoryMapsRandom(first: 10) { id }
        }
    """
    variables = {"storyMapId": story_map.story_map_id}
    assert (
        len(client_query_no_token(query, variables=variables).json()["data"]["storyMaps"]["edges"])
        == 1
    )
    response = logged_client.post(
        reverse("story_map:update"), data={"id": story_map.pk, "unpublish": "true"}
    )
    assert response.status_code == 201

    visitor_data = client_query_no_token(query, variables=variables).json()["data"]
    assert visitor_data["storyMaps"]["edges"] == []
    assert visitor_data["featuredStoryMapsRandom"] == []
    owner_data = client_query(query, variables=variables).json()["data"]
    node = owner_data["storyMaps"]["edges"][0]["node"]
    assert node["isPublished"] is False
    assert json.loads(node["configuration"])["title"] == "Draft"


@pytest.mark.parametrize("access", ["owner", "approved", "pending", "nonmember", "anonymous"])
@pytest.mark.parametrize("is_published", [True, False])
@mock.patch("apps.story_map.services.story_map_media_upload_service.get_signed_url")
def test_configuration_access_respects_membership(
    signed_url, client_query, client_query_no_token, users, access, is_published
):
    membership_list = mixer.blend(MembershipList)
    if access in ("approved", "pending"):
        mixer.blend(
            Membership,
            membership_list=membership_list,
            user=users[0],
            membership_status=Membership.APPROVED if access == "approved" else Membership.PENDING,
        )
    story_map = mixer.blend(
        StoryMap,
        created_by=users[0] if access == "owner" else users[1],
        membership_list=membership_list,
        story_map_id="access01",
        is_published=is_published,
        configuration={"title": "Private draft", "featuredImage": {"url": "draft-key"}},
        published_configuration={
            "title": "Public snapshot",
            "featuredImage": {"url": "public-key"},
        },
    )
    signed_url.return_value = "signed"
    query = """
        query Access($id: String!) {
          storyMaps(storyMapId: $id) {
            edges { node { configuration publishedConfiguration } }
          }
        }
    """
    query_as_user = client_query_no_token if access == "anonymous" else client_query
    body = query_as_user(query, variables={"id": story_map.story_map_id}).json()
    assert "errors" not in body
    edges = body["data"]["storyMaps"]["edges"]
    if not is_published and access in ("nonmember", "anonymous"):
        assert edges == []
        return

    node = edges[0]["node"]
    can_edit = access in ("owner", "approved")
    if can_edit:
        assert json.loads(node["configuration"])["title"] == "Private draft"
    else:
        assert node["configuration"] is None
    if is_published or can_edit:
        assert json.loads(node["publishedConfiguration"])["title"] == "Public snapshot"
    else:
        assert node["publishedConfiguration"] is None
    signed_keys = [call.args[0] for call in signed_url.call_args_list]
    assert ("draft-key" in signed_keys) == can_edit
    assert ("public-key" in signed_keys) == (is_published or can_edit)


def test_public_slug_lookup_stays_on_published_version_until_republication(
    logged_client, client_query_no_token, users
):
    published = {"title": "Public title", "chapters": []}
    story_map = mixer.blend(
        StoryMap,
        created_by=users[0],
        title="Public title",
        configuration=published,
        published_configuration=published,
        is_published=True,
    )
    query = """
        query MapByUrl($storyMapId: String!, $slug: String!) {
          storyMaps(storyMapId: $storyMapId, slug: $slug) {
            edges { node { id slug publishedConfiguration } }
          }
        }
    """

    def lookup(slug):
        response = client_query_no_token(
            query, variables={"storyMapId": story_map.story_map_id, "slug": slug}
        )
        return response.json()["data"]["storyMaps"]["edges"]

    data = {
        "id": story_map.pk,
        "title": "Private revision",
        "configuration": json.dumps({"title": "Private revision", "chapters": []}),
        "publish": "false",
    }
    assert logged_client.post(reverse("story_map:update"), data=data).status_code == 201
    node = lookup("public-title")[0]["node"]
    assert json.loads(node["publishedConfiguration"]) == published
    assert lookup("private-revision") == []

    data["publish"] = "true"
    assert logged_client.post(reverse("story_map:update"), data=data).status_code == 201
    assert lookup("public-title") == []
    assert lookup("private-revision")[0]["node"]["id"] == str(story_map.id)


def test_empty_slug_filter_matches_only_empty_slug(client_query_no_token):
    empty = mixer.blend(StoryMap, story_map_id="same-id", title="!!!", is_published=True)
    slugged = mixer.blend(StoryMap, story_map_id="same-id", title="A map", is_published=True)
    query = """
        query Maps($id: String!, $slug: String) {
          storyMaps(storyMapId: $id, slug: $slug) { edges { node { id } } }
        }
    """

    def ids(variables):
        edges = client_query_no_token(query, variables=variables).json()["data"]["storyMaps"][
            "edges"
        ]
        return {edge["node"]["id"] for edge in edges}

    assert ids({"id": "same-id", "slug": ""}) == {str(empty.id)}
    assert ids({"id": "same-id", "slug": "a-map"}) == {str(slugged.id)}
    assert ids({"id": "same-id"}) == {str(empty.id), str(slugged.id)}


def test_story_maps_query(client_query, story_maps, users):
    story_maps[0].featured = True
    story_maps[0].save(update_fields=["featured"])

    response = client_query(
        """
        {storyMaps {
          edges {
            node {
              id
              title
              featured
              isPublished
              configuration
              publishedConfiguration
              createdBy {
                id
              }
            }
          }
        }}
        """
    )

    edges = response.json()["data"]["storyMaps"]["edges"]
    entries_result = [edge["node"] for edge in edges]

    assert len(entries_result) == 9
    for story_map in entries_result:
        assert story_map["isPublished"] is True or story_map["createdBy"]["id"] == str(users[0].id)
        if story_map["id"] == str(story_maps[0].id):
            assert story_map["featured"] is True
        if story_map["isPublished"]:
            assert story_map["configuration"] != story_map["publishedConfiguration"]


def test_story_maps_filter_by_featured(client_query, story_maps):
    visible_featured_story_map = story_maps[0]
    hidden_featured_story_map = story_maps[9]

    visible_featured_story_map.featured = True
    visible_featured_story_map.save(update_fields=["featured"])
    hidden_featured_story_map.featured = True
    hidden_featured_story_map.save(update_fields=["featured"])

    response = client_query(
        """
        {storyMaps(featured: true) {
          edges {
            node {
              id
              featured
            }
          }
        }}
        """
    )

    edges = response.json()["data"]["storyMaps"]["edges"]
    story_maps_result = [edge["node"] for edge in edges]

    assert story_maps_result == [
        {
            "id": str(visible_featured_story_map.id),
            "featured": True,
        }
    ]


def test_featured_story_maps_random_returns_published_random_subset(client_query, story_maps):
    visible_featured_story_maps = [story_maps[0], story_maps[1], story_maps[5], story_maps[6]]
    unpublished_featured_story_map = story_maps[2]
    hidden_featured_story_map = story_maps[9]

    for story_map in visible_featured_story_maps:
        story_map.featured = True
        story_map.save(update_fields=["featured"])

    unpublished_featured_story_map.featured = True
    unpublished_featured_story_map.save(update_fields=["featured"])
    hidden_featured_story_map.featured = True
    hidden_featured_story_map.save(update_fields=["featured"])

    response = client_query(
        """
        query FeaturedStoryMapsRandom($first: Int!) {
          featuredStoryMapsRandom(first: $first) {
            id
            featured
          }
        }
        """,
        variables={"first": 3},
    )

    story_maps_result = response.json()["data"]["featuredStoryMapsRandom"]
    visible_featured_ids = {str(story_map.id) for story_map in visible_featured_story_maps}

    assert len(story_maps_result) == 3
    assert {story_map["id"] for story_map in story_maps_result}.issubset(visible_featured_ids)
    assert all(story_map["featured"] is True for story_map in story_maps_result)


def test_story_maps_filter_by_can_change_by_email(client_query, story_maps, users):
    response = client_query(
        f"""
        {{storyMaps(memberships_User_Email_Not: "{users[0].email}") {{
          edges {{
            node {{
              id
              createdBy {{
                email
              }}
            }}
          }}
        }}}}
        """
    )

    edges = response.json()["data"]["storyMaps"]["edges"]
    story_maps_result = [edge["node"]["createdBy"]["email"] for edge in edges]

    assert len(story_maps_result) == 4
    assert str(users[0].email) not in story_maps_result


def test_anonymous_cannot_see_ownerless_unpublished_story_map(client_query_no_token):
    assert AnonymousUser().pk is None
    draft = mixer.blend(
        StoryMap,
        title="Ownerless draft",
        story_map_id="draft001",
        created_by=None,
        membership_list=None,
        is_published=False,
    )
    published = mixer.blend(
        StoryMap,
        title="Ownerless published map",
        story_map_id="publish001",
        created_by=None,
        membership_list=None,
        is_published=True,
    )
    response = client_query_no_token(
        """
        query OwnerlessMaps($draftId: String!) {
          storyMaps { edges { node { id } } }
          draft: storyMaps(storyMapId: $draftId) { edges { node { id } } }
        }
        """,
        variables={"draftId": draft.story_map_id},
    )
    body = response.json()
    assert "errors" not in body
    assert body["data"]["draft"]["edges"] == []
    assert [edge["node"]["id"] for edge in body["data"]["storyMaps"]["edges"]] == [
        str(published.pk)
    ]


def test_story_maps_anonymous_user(client_query_no_token, story_maps):
    response = client_query_no_token(
        """
        {storyMaps {
          edges {
            node {
              title
              isPublished
              createdBy {
                id
              }
              membershipList {
                id
              }
              configuration
              publishedConfiguration
            }
          }
        }}
        """
    )

    edges = response.json()["data"]["storyMaps"]["edges"]
    entries_result = [edge["node"] for edge in edges]

    assert len(entries_result) == 6
    for story_map in entries_result:
        assert story_map["isPublished"] is True
        assert story_map["membershipList"] is None
        assert story_map["configuration"] is None
        assert story_map["publishedConfiguration"] is not None


def test_story_map_by_membership_email_filter_no_results(client_query, users):
    response = client_query(
        f"""
        {{storyMaps(memberships_User_Email: "{users[2].email}") {{
          edges {{
            node {{
              id
              createdBy {{
                email
              }}
            }}
          }}
        }}}}
        """
    )

    edges = response.json()["data"]["storyMaps"]["edges"]
    story_maps_result = [edge["node"] for edge in edges]

    assert len(story_maps_result) == 0


def test_story_map_by_membership_email_filter(client_query, story_map_user_memberships, users):
    membership = story_map_user_memberships[0]
    membership.user = users[2]
    membership.save()

    response = client_query(
        f"""
        {{storyMaps(memberships_User_Email: "{users[2].email}") {{
          edges {{
            node {{
              id
              createdBy {{
                email
              }}
            }}
          }}
        }}}}
        """
    )

    edges = response.json()["data"]["storyMaps"]["edges"]
    story_maps_result = [edge["node"] for edge in edges]

    assert len(story_maps_result) == 1


def test_story_map_by_membership_email_not_filter(client_query, story_map_user_memberships, users):
    response = client_query(
        f"""
        {{storyMaps(memberships_User_Email_Not: "{users[0].email}") {{
          edges {{
            node {{
              id
              createdBy {{
                email
              }}
            }}
          }}
        }}}}
        """
    )

    edges = response.json()["data"]["storyMaps"]["edges"]
    story_maps_result = [edge["node"] for edge in edges]

    assert len(story_maps_result) == 4


@mock.patch("apps.story_map.services.story_map_media_upload_service.get_signed_url")
def test_story_maps_published_media_signed_url(
    mocked_get_signed_url, client_query, story_maps, users
):
    mixer.blend(
        StoryMap,
        created_by=users[0],
        is_published=True,
        published_configuration={
            "title": "Published with Featured Image",
            "featuredImage": {"url": "test_featured_url", "type": "image/jpeg"},
            "chapters": [{"media": {"type": "image", "url": "test_chapter_url"}}],
        },
        configuration={"title": "Draft"},
    )

    mocked_get_signed_url.return_value = "signed_url"
    response = client_query(
        """
        {storyMaps {
          edges {
            node {
              isPublished
              publishedConfiguration
            }
          }
        }}
        """
    )

    assert mocked_get_signed_url.call_count >= 2

    story_maps_data = response.json()["data"]["storyMaps"]["edges"]
    featured_story = next(
        (
            edge["node"]
            for edge in story_maps_data
            if edge["node"]["publishedConfiguration"]
            and json.loads(edge["node"]["publishedConfiguration"]).get("featuredImage")
        ),
        None,
    )
    assert featured_story is not None
    published_config = json.loads(featured_story["publishedConfiguration"])
    assert published_config["featuredImage"]["signedUrl"] == "signed_url"


def test_story_map_owner_can_see_memberships_without_being_member(client_query, users):
    owner = users[0]
    collaborator = users[2]

    story_map = mixer.blend(StoryMap, created_by=owner, is_published=False)
    membership_list = mixer.blend(
        MembershipList,
        enroll_method=MembershipList.ENROLL_METHOD_INVITE,
        membership_type=MembershipList.MEMBERSHIP_TYPE_CLOSED,
    )
    story_map.membership_list = membership_list
    story_map.save()

    mixer.blend(
        Membership,
        membership_list=membership_list,
        user=collaborator,
        user_role="editor",
        membership_status="pending",
    )

    response = client_query(
        """
        query StoryMapWithMemberships($id: ID!) {
          storyMap(id: $id) {
            membershipList {
              memberships {
                edges {
                  node {
                    user { email }
                    membershipStatus
                  }
                }
              }
            }
          }
        }
        """,
        variables={"id": str(story_map.pk)},
    )

    story_map_data = response.json()["data"]["storyMap"]
    memberships = story_map_data["membershipList"]["memberships"]["edges"]

    assert len(memberships) == 1
    assert memberships[0]["node"]["user"]["email"] == collaborator.email
    assert memberships[0]["node"]["membershipStatus"] == "PENDING"
