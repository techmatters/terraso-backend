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
from apps.core.models import Group, Landscape


def is_target_manager(user, target):
    if isinstance(target, Group):
        return (
            target.membership_list.memberships.by_role(group_collaboration_roles.ROLE_MANAGER)
            .filter(user=user)
            .exists()
        )
    if isinstance(target, Landscape):
        return (
            target.membership_list.memberships.by_role(landscape_collaboration_roles.ROLE_MANAGER)
            .filter(user=user)
            .exists()
        )
    return False


def is_target_member(user, target):
    return target.membership_list.memberships.approved_only().filter(user=user).exists()


def is_user_allowed_to_view_data_entry(data_entry, user):
    shared_resources = data_entry.shared_resources.all()
    for shared_resource in shared_resources:
        if is_target_member(user, shared_resource.target):
            return True
    return False


def is_user_allowed_to_change_data_entry(data_entry, user):
    shared_resources = data_entry.shared_resources.all()
    for shared_resource in shared_resources:
        if is_target_manager(user, shared_resource.target):
            return True
    return False


@rules.predicate
def allowed_to_change_data_entry(user, data_entry):
    return data_entry.created_by == user


@rules.predicate
def allowed_to_delete_data_entry(user, data_entry):
    if data_entry.created_by == user:
        return True
    shared_resources = data_entry.shared_resources.all()
    for shared_resource in shared_resources:
        if is_target_manager(user, shared_resource.target):
            return True
    return False


@rules.predicate
def allowed_to_add_data_entry(user, target):
    return is_target_member(user, target)


@rules.predicate
def allowed_to_view_data_entry(user, data_entry):
    return is_user_allowed_to_view_data_entry(data_entry, user)


@rules.predicate
def allowed_to_view_visualization_config(user, visualization_config):
    return is_user_allowed_to_view_data_entry(visualization_config.data_entry, user)


@rules.predicate
def allowed_to_add_visualization_config(user, data_entry):
    return is_user_allowed_to_view_data_entry(data_entry, user)


@rules.predicate
def allowed_to_change_visualization_config(user, visualization_config):
    return visualization_config.created_by == user


@rules.predicate
def allowed_to_delete_visualization_config(user, visualization_config):
    if visualization_config.created_by == user:
        return True
    return is_user_allowed_to_change_data_entry(visualization_config.data_entry, user)


rules.add_rule("allowed_to_add_data_entry", allowed_to_add_data_entry)
