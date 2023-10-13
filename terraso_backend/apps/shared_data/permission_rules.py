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

from apps.core.models import Group, Landscape


def is_target_manager(user, target):
    if isinstance(target, Group):
        return user.memberships.managers_only().filter(group=target).exists()
    if isinstance(target, Landscape):
        return user.memberships.managers_only().filter(group=target.get_default_group()).exists()
    return False


def is_target_member(user, target):
    if isinstance(target, Group):
        return user.memberships.approved_only().filter(group=target).exists()
    if isinstance(target, Landscape):
        return user.memberships.approved_only().filter(group=target.get_default_group()).exists()
    return False


def is_user_allowed_to_view_data_entry(data_entry, user):
    shared_targets = data_entry.shared_targets.all()
    for shared_target in shared_targets:
        if is_target_member(user, shared_target.target):
            return True


def is_user_allowed_to_change_data_entry(data_entry, user):
    shared_targets = data_entry.shared_targets.all()
    for shared_target in shared_targets:
        if is_target_manager(user, shared_target.target):
            return True


@rules.predicate
def allowed_to_change_data_entry(user, data_entry):
    return data_entry.created_by == user


@rules.predicate
def allowed_to_delete_data_entry(user, data_entry):
    if data_entry.created_by == user:
        return True
    shared_targets = data_entry.shared_targets.all()
    for shared_target in shared_targets:
        if is_target_manager(user, shared_target.target):
            return True
    return False


@rules.predicate
def allowed_to_add_data_entry(user, target):
    return is_target_manager(user, target)


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
