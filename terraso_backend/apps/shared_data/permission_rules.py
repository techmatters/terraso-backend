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


@rules.predicate
def allowed_to_change_data_entry(user, data_entry):
    return data_entry.created_by == user


@rules.predicate
def allowed_to_delete_data_entry(user, data_entry):
    return (
        data_entry.created_by == user
        or user.memberships.managers_only().filter(group__in=data_entry.groups.all()).exists()
    )


@rules.predicate
def allowed_to_view_data_entry(user, data_entry):
    return user.memberships.filter(group__in=data_entry.groups.all()).exists()


@rules.predicate
def allowed_to_view_visualization_config(user, visualization_config):
    return user.memberships.filter(group__in=visualization_config.data_entry.groups.all()).exists()


@rules.predicate
def allowed_to_change_visualization_config(user, visualization_config):
    return visualization_config.created_by == user


@rules.predicate
def allowed_to_delete_visualization_config(user, visualization_config):
    return (
        visualization_config.created_by == user
        or user.memberships.managers_only()
        .filter(group__in=visualization_config.data_entry.groups.all())
        .exists()
    )
