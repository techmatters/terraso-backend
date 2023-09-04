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

import pytest

pytestmark = pytest.mark.django_db


def test_story_maps_query(client_query, story_maps, users):
    response = client_query(
        """
        {storyMaps {
          edges {
            node {
              title
              isPublished
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
    print(f"memberships: {membership}")
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
