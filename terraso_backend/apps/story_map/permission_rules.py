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

import rules


@rules.predicate
def allowed_to_view_story_map(user, story_map):
    return story_map.is_published


@rules.predicate
def allowed_to_change_story_map(user, story_map):
    return story_map.created_by == user


@rules.predicate
def allowed_to_delete_story_map(user, story_map):
    return story_map.created_by == user


@rules.predicate
def allowed_to_save_membership(user, obj):
    story_map = obj.get("story_map")
    is_owner = story_map.created_by == user
    return is_owner


@rules.predicate
def allowed_to_delete_membership(user, obj):
    story_map = obj.get("story_map")
    membership = obj.get("membership")
    is_owner = story_map.created_by == user
    if is_owner:
        return True
    return membership.user_email == user.email


rules.add_rule("allowed_to_change_story_map", allowed_to_change_story_map)
