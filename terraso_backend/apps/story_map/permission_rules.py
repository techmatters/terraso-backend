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

from apps.collaboration.models import Membership

from .collaboration_roles import ROLE_COLLABORATOR


@rules.predicate
def allowed_to_view_story_map(user, story_map):
    return story_map.is_published


@rules.predicate
def allowed_to_change_story_map(user, story_map):
    is_owner = story_map.created_by == user
    if is_owner:
        return True
    account_membership = (
        story_map.membership_list.memberships.approved_only().filter(user=user).first()
    )
    return account_membership is not None and account_membership.user_role == ROLE_COLLABORATOR


@rules.predicate
def allowed_to_delete_story_map(user, story_map):
    return story_map.created_by == user


@rules.predicate
def allowed_to_change_story_map_membership(user, obj):
    story_map = obj.get("story_map")

    is_story_map_owner = story_map.created_by == user
    if is_story_map_owner:
        return True

    current_membership = obj.get("current_membership")
    is_new = not current_membership
    if not is_new:
        # Only owners can update a membership
        return False

    requestor_membership = obj.get("requestor_membership")
    requestor_is_member = requestor_membership is not None

    is_collaborator = (
        requestor_is_member
        and requestor_membership.user_role == ROLE_COLLABORATOR
        and requestor_membership.membership_status == Membership.APPROVED
    )
    if is_collaborator:
        return True

    return False


@rules.predicate
def allowed_to_approve_story_map_membership(user, obj):
    membership = obj.get("membership")
    is_user_membership = membership.user.email == user.email
    return is_user_membership


@rules.predicate
def allowed_to_approve_story_map_membership_token(user, obj):
    membership = obj.get("membership")
    decoded_token = obj.get("decoded_token")
    pending_email = decoded_token.get("pendingEmail")
    membership_id = decoded_token.get("membershipId")
    is_valid_membership_for_token = (
        membership_id == str(membership.id)
        and pending_email is not None
        and pending_email == membership.pending_email
    )
    return is_valid_membership_for_token


@rules.predicate
def allowed_to_delete_story_map_membership(user, obj):
    story_map = obj.get("story_map")
    membership = obj.get("membership")
    is_owner = story_map.created_by == user
    if is_owner:
        return True
    return membership.user.email == user.email


rules.add_rule("allowed_to_change_story_map", allowed_to_change_story_map)
rules.add_rule("allowed_to_delete_story_map", allowed_to_delete_story_map)
rules.add_rule("allowed_to_change_story_map_membership", allowed_to_change_story_map_membership)
rules.add_rule("allowed_to_approve_story_map_membership", allowed_to_approve_story_map_membership)
rules.add_rule(
    "allowed_to_approve_story_map_membership_token", allowed_to_approve_story_map_membership_token
)
rules.add_rule("allowed_to_delete_story_map_membership", allowed_to_delete_story_map_membership)
