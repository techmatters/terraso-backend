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


@rules.predicate
def allowed_group_managers_count(user, membership_id):
    from apps.core.models import Membership

    membership = Membership.objects.get(pk=membership_id)
    is_user_manager = user.is_group_manager(membership.group.id)
    managers_count = membership.membership_list.memberships.by_role(
        group_collaboration_roles.ROLE_MANAGER
    ).count()
    is_own_membership = user.collaboration_memberships.filter(pk=membership_id).exists()

    # User is the last manager and a Group cannot have no managers
    if managers_count == 1 and is_user_manager and is_own_membership:
        return False

    return True


@rules.predicate
def allowed_landscape_managers_count(user, obj):
    membership = obj.get("membership")
    landscape = obj.get("landscape")

    is_user_manager = landscape.membership_list.has_role(
        user, landscape_collaboration_roles.ROLE_MANAGER
    )
    managers_count = landscape.membership_list.memberships.by_role(
        landscape_collaboration_roles.ROLE_MANAGER
    ).count()
    is_own_membership = user.collaboration_memberships.filter(pk=membership.id).exists()

    # User is the last manager and a Group cannot have no managers
    if managers_count == 1 and is_user_manager and is_own_membership:
        return False

    return True


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


@rules.predicate
def allowed_to_change_landscape_membership(user, obj):
    landscape = obj.get("landscape")
    user_role = obj.get("user_role")
    user_exists = obj.get("user_exists")
    user_email = obj.get("user_email")
    is_landscape_manager = user.is_landscape_manager(landscape.id)
    own_membership = user_email == user.email

    if not user_exists:
        return False

    if (
        not is_landscape_manager
        and own_membership
        and user_role == landscape_collaboration_roles.ROLE_MEMBER
    ):
        return True

    return is_landscape_manager


@rules.predicate
def allowed_to_change_group_membership(user, obj):
    group = obj.get("group")
    user_role = obj.get("user_role")
    user_exists = obj.get("user_exists")
    user_email = obj.get("user_email")
    is_manager = user.is_group_manager(group.id)
    own_membership = user_email == user.email

    if not user_exists:
        return False

    if not is_manager and own_membership and user_role == group_collaboration_roles.ROLE_MEMBER:
        return True

    return is_manager


@rules.predicate
def allowed_to_delete_landscape_membership(user, obj):
    landscape = obj.get("landscape")
    membership = obj.get("membership")

    if user.is_landscape_manager(landscape.id):
        return True

    return membership.user.email == user.email


rules.add_rule("allowed_group_managers_count", allowed_group_managers_count)
rules.add_rule("allowed_to_update_preferences", allowed_to_update_preferences)
rules.add_rule("allowed_to_change_landscape", allowed_to_change_landscape)
rules.add_rule("allowed_to_change_landscape_membership", allowed_to_change_landscape_membership)
rules.add_rule("allowed_to_delete_landscape_membership", allowed_to_delete_landscape_membership)
rules.add_rule("allowed_landscape_managers_count", allowed_landscape_managers_count)
rules.add_rule("allowed_to_change_group_membership", allowed_to_change_group_membership)
