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
from mixer.backend.django import mixer

from apps.collaboration.models import Membership, MembershipList
from apps.story_map.models import StoryMap

pytestmark = pytest.mark.django_db


def test_story_maps_query(client_query, story_maps, users):
    response = client_query(
        """
        {storyMaps {
          edges {
            node {
              title
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
        if story_map["isPublished"]:
            assert story_map["configuration"] != story_map["publishedConfiguration"]


def test_story_maps_filter_by_can_change_by_email(client_query, story_maps, users):
    response = client_query(
        """
        {storyMaps(memberships_User_Email_Not: "%s") {
          edges {
            node {
              id
              createdBy {
                email
              }
            }
          }
        }}
        """
        % users[0].email
    )

    edges = response.json()["data"]["storyMaps"]["edges"]
    story_maps_result = [edge["node"]["createdBy"]["email"] for edge in edges]

    assert len(story_maps_result) == 4
    assert str(users[0].email) not in story_maps_result


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
        """
        {storyMaps(memberships_User_Email: "%s") {
          edges {
            node {
              id
              createdBy {
                email
              }
            }
          }
        }}
        """
        % users[2].email
    )

    edges = response.json()["data"]["storyMaps"]["edges"]
    story_maps_result = [edge["node"] for edge in edges]

    assert len(story_maps_result) == 0


def test_story_map_by_membership_email_filter(client_query, story_map_user_memberships, users):
    membership = story_map_user_memberships[0]
    membership.user = users[2]
    membership.save()

    response = client_query(
        """
        {storyMaps(memberships_User_Email: "%s") {
          edges {
            node {
              id
              createdBy {
                email
              }
            }
          }
        }}
        """
        % users[2].email
    )

    edges = response.json()["data"]["storyMaps"]["edges"]
    story_maps_result = [edge["node"] for edge in edges]

    assert len(story_maps_result) == 1


def test_story_map_by_membership_email_not_filter(client_query, story_map_user_memberships, users):
    response = client_query(
        """
        {storyMaps(memberships_User_Email_Not: "%s") {
          edges {
            node {
              id
              createdBy {
                email
              }
            }
          }
        }}
        """
        % users[0].email
    )

    edges = response.json()["data"]["storyMaps"]["edges"]
    story_maps_result = [edge["node"] for edge in edges]

    assert len(story_maps_result) == 4


@mock.patch("apps.graphql.schema.story_maps.story_map_media_upload_service.get_signed_url")
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
