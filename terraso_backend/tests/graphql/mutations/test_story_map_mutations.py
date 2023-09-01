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

import pytest

from apps.story_map.models import StoryMap

pytestmark = pytest.mark.django_db


def test_story_map_delete_by_creator_works(client_query, story_maps):
    old_story_map = story_maps[0]

    response = client_query(
        """
        mutation deleteStoryMap($input: StoryMapDeleteMutationInput!){
          deleteStoryMap(input: $input) {
            storyMap {
              title
            }
          }
        }

        """,
        variables={"input": {"id": str(old_story_map.id)}},
    )

    story_map_result = response.json()["data"]["deleteStoryMap"]["storyMap"]

    assert story_map_result["title"] == old_story_map.title
    assert not StoryMap.objects.filter(title=story_map_result["title"])


def test_story_map_delete_by_non_creator_fails_due_permission_check(
    client_query, story_maps, users
):
    old_story_map = story_maps[0]

    # Let's force old data creator be different from client query user
    old_story_map.created_by = users[2]
    old_story_map.save()

    response = client_query(
        """
        mutation deleteStoryMap($input: StoryMapDeleteMutationInput!){
          deleteStoryMap(input: $input) {
            storyMap {
              title
            }
            errors
          }
        }

        """,
        variables={"input": {"id": str(old_story_map.id)}},
    )

    response = response.json()

    assert "errors" in response["data"]["deleteStoryMap"]
    assert "delete_not_allowed" in response["data"]["deleteStoryMap"]["errors"][0]["message"]


def test_story_map_save_membership_by_creator_works(client_query, story_maps, users):
    old_story_map = story_maps[0]

    old_story_map.created_by = users[0]
    old_story_map.save()

    response = client_query(
        """
        mutation saveStoryMapMembership($input: StoryMapMembershipSaveMutationInput!){
          saveStoryMapMembership(input: $input) {
            memberships {
              id
              membershipStatus
            }
            errors
          }
        }
        """,
        variables={
            "input": {
                "storyMapId": str(old_story_map.story_map_id),
                "storyMapSlug": old_story_map.slug,
                "userRole": "collaborator",
                "userEmails": [users[1].email, users[2].email],
            }
        },
    )
    json_response = response.json()

    assert json_response["data"]["saveStoryMapMembership"]["errors"] is None

    print(f"json_response: {json_response}")
    memberships_result = json_response["data"]["saveStoryMapMembership"]["memberships"]

    print(f"memberships_result: {memberships_result}")
    assert len(memberships_result) == 2
    assert old_story_map.membership_list.memberships.count() == 2
    assert memberships_result[0]["membershipStatus"] == "PENDING"
    assert memberships_result[1]["membershipStatus"] == "PENDING"


def test_story_map_save_membership_by_non_creator_fails_due_permission_check(
    client_query, story_maps, users
):
    old_story_map = story_maps[0]

    old_story_map.created_by = users[2]
    old_story_map.save()

    response = client_query(
        """
        mutation saveStoryMapMembership($input: StoryMapMembershipSaveMutationInput!){
          saveStoryMapMembership(input: $input) {
            memberships {
              id
              membershipStatus
            }
            errors
          }
        }
        """,
        variables={
            "input": {
                "storyMapId": str(old_story_map.story_map_id),
                "storyMapSlug": old_story_map.slug,
                "userRole": "collaborator",
                "userEmails": [users[1].email, users[2].email],
            }
        },
    )
    json_response = response.json()
    print(f"json_response: {json_response}")

    assert "errors" in json_response["data"]["saveStoryMapMembership"]
    error_result = response.json()["data"]["saveStoryMapMembership"]["errors"][0]["message"]
    json_error = json.loads(error_result)
    assert json_error[0]["code"] == "update_not_allowed"
