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
