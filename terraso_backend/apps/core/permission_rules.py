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

import rules

from apps.core import group_collaboration_roles, landscape_collaboration_roles


def get_manager_role(entity):
    from apps.core.models import Group, Landscape

    if isinstance(entity, Group):
        return group_collaboration_roles.ROLE_MANAGER
    if isinstance(entity, Landscape):
        return landscape_collaboration_roles.ROLE_MANAGER


@rules.predicate
def allowed_to_change_group(user, group_id):
    return user.is_group_manager(group_id)


@rules.predicate
def allowed_to_delete_group(user, group_id):
    return user.is_group_manager(group_id)


@rules.predicate
def allowed_to_add_group_association(user, parent_group_id):
    return user.is_group_manager(parent_group_id)


@rules.predicate
def allowed_to_delete_group_association(user, group_association):
    return user.is_group_manager(group_association.parent_group.pk) or user.is_group_manager(
        group_association.child_group.pk
    )


@rules.predicate
def allowed_to_change_landscape(user, landscape_id):
    return user.is_landscape_manager(landscape_id)


@rules.predicate
def allowed_to_delete_landscape(user, landscape_id):
    return user.is_landscape_manager(landscape_id)


@rules.predicate
def allowed_to_add_landscape_group(user, landscape_id):
    return user.is_landscape_manager(landscape_id)


@rules.predicate
def allowed_to_delete_landscape_group(user, landscape_group):
    return user.is_landscape_manager(landscape_group.landscape.id) or user.is_group_manager(
        landscape_group.group.id
    )


def validate_managers_count(user, membership, entity):
    """
    Validates if the count of managers in an entity is valid after a user's membership change.
    The count of managers is valid if there is at least one manager left after the change.

    Parameters:
    user (User): The user whose membership is being changed.
    membership (Membership): The membership object that is being changed.
    entity (Entity): The entity (group or landscape) in which the membership change is happening.

    Returns:
    bool: True if the count of managers is valid after the membership change, False otherwise.
    """
    manager_role = get_manager_role(entity)
    is_manager = entity.membership_list.has_role(user, manager_role)
    managers_count = entity.membership_list.memberships.by_role(manager_role).count()
    is_own_membership = user.collaboration_memberships.filter(pk=membership.id).exists()

    return not (managers_count == 1 and is_manager and is_own_membership)


@rules.predicate
def allowed_group_managers_count(user, obj):
    membership = obj.get("membership")
    group = obj.get("group")

    return validate_managers_count(user, membership, entity=group)


@rules.predicate
def allowed_landscape_managers_count(user, obj):
    membership = obj.get("membership")
    landscape = obj.get("landscape")

    return validate_managers_count(user, membership, entity=landscape)


@rules.predicate
def allowed_to_update_preferences(user, user_preferences):
    return user_preferences.user.id == user.id


@rules.predicate
def allowed_to_change_project(user, project):
    return project.is_manager(user)


@rules.predicate
def allowed_to_update_site(user, site):
    if not site.owned_by_user:
        return site.project.is_manager(user)
    return site.owner == user


def validate_change_membership(user, entity, obj):
    """
    Validates if a user is allowed to change the membership of an entity.

    Parameters:
    user (User): The user attempting to change the membership.
    entity (Entity): The entity whose membership is being changed (group or landscape).
    obj (dict): A dictionary containing details about the membership change.
                 It should contain the following keys:
                 - "user_role": The role the user will have after the change.
                 - "user_exists": A boolean indicating if the user is already registered.
                 - "user_email": The email of the user whose membership is being changed.

    Returns:
    bool: True if the user is allowed to change the membership, False otherwise.
    """
    user_role = obj.get("user_role")
    user_exists = obj.get("user_exists")
    user_email = obj.get("user_email")

    manager_role = get_manager_role(entity)
    is_manager = entity.membership_list.has_role(user, manager_role)

    own_membership = user_email == user.email

    if not user_exists:
        return False

    if not is_manager and own_membership and user_role != manager_role:
        return True

    return is_manager


@rules.predicate
def allowed_to_change_landscape_membership(user, obj):
    landscape = obj.get("landscape")

    return validate_change_membership(user, landscape, obj)


@rules.predicate
def allowed_to_change_group_membership(user, obj):
    from apps.collaboration.models import Membership as CollaborationMembership

    group = obj.get("group")
    current_membership = obj.get("current_membership")
    new_membership_status = obj.get("membership_status")
    manager_role = get_manager_role(group)
    is_manager = group.membership_list.has_role(user, manager_role)

    is_approving = (
        current_membership
        and current_membership.membership_status == CollaborationMembership.PENDING
        and new_membership_status == CollaborationMembership.APPROVED
    )

    if is_approving and not is_manager:
        return False

    return validate_change_membership(user, group, obj)


def validate_delete_membership(user, entity, membership):
    manager_role = get_manager_role(entity)
    is_manager = entity.membership_list.has_role(user, manager_role)

    if is_manager:
        return True

    return membership.user.email == user.email


@rules.predicate
def allowed_to_delete_landscape_membership(user, obj):
    landscape = obj.get("landscape")
    membership = obj.get("membership")

    return validate_delete_membership(user, landscape, membership)


@rules.predicate
def allowed_to_delete_group_membership(user, obj):
    group = obj.get("group")
    membership = obj.get("membership")

    return validate_delete_membership(user, group, membership)


rules.add_rule("allowed_group_managers_count", allowed_group_managers_count)
rules.add_rule("allowed_to_update_preferences", allowed_to_update_preferences)
rules.add_rule("allowed_to_change_landscape", allowed_to_change_landscape)
rules.add_rule("allowed_to_change_landscape_membership", allowed_to_change_landscape_membership)
rules.add_rule("allowed_to_delete_landscape_membership", allowed_to_delete_landscape_membership)
rules.add_rule("allowed_landscape_managers_count", allowed_landscape_managers_count)
rules.add_rule("allowed_to_change_group_membership", allowed_to_change_group_membership)
rules.add_rule("allowed_to_delete_group_membership", allowed_to_delete_group_membership)
