# Copyright © 2024 Technology Matters
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

from enum import Enum, auto

from apps.core.models import User
from apps.project_management.permission_rules import Context


class ProjectAction(Enum):
    CREATE = (auto(),)
    UPDATE_REQUIREMENTS = (auto(),)
    EDIT_PINNED_NOTE = (auto(),)
    ARCHIVE = (auto(),)
    ADD_MEMBER = (auto(),)
    CHANGE_USER_ROLE = (auto(),)
    DELETE_USER = (auto(),)
    DELETE = (auto(),)
    GENERATE_LINK = (auto(),)
    CHANGE_REQUIRED_DEPTH_INTERVAL = (auto(),)
    LEAVE = (auto(),)
    ADD_NEW_SITE = (auto(),)
    ADD_UNAFFILIATED_SITE = (auto(),)
    TRANSFER_AFFILIATED_SITE = (auto(),)


class SiteAction(Enum):
    CREATE = (auto(),)
    UPDATE_SETTINGS = (auto(),)
    ENTER_DATA = (auto(),)
    DELETE = (auto(),)
    CREATE_NOTE = (auto(),)
    EDIT_NOTE = (auto(),)
    DELETE_NOTE = (auto(),)
    UPDATE_DEPTH_INTERVAL = (auto(),)


PROJECT_TABLE = {
    ProjectAction.CREATE: "allowed_to_create",
    ProjectAction.UPDATE_REQUIREMENTS: "allowed_to_manage_project",
    ProjectAction.EDIT_PINNED_NOTE: "allowed_to_manage_project",
    ProjectAction.ARCHIVE: "allowed_to_manage_project",
    ProjectAction.ADD_MEMBER: "allowed_to_manage_project",
    ProjectAction.CHANGE_USER_ROLE: "allowed_to_manage_project",
    ProjectAction.DELETE_USER: "allowed_to_manage_project",
    ProjectAction.DELETE: "allowed_to_manage_project",
    ProjectAction.GENERATE_LINK: "allowed_to_manage_project",
    ProjectAction.CHANGE_REQUIRED_DEPTH_INTERVAL: "allowed_to_manage_project",
    ProjectAction.LEAVE: "is_project_member",
    ProjectAction.ADD_NEW_SITE: "allowed_to_add_new_site_to_project",
    ProjectAction.ADD_UNAFFILIATED_SITE: "allowed_to_add_unaffiliated_site_to_project",
    ProjectAction.TRANSFER_AFFILIATED_SITE: "allowed_to_transfer_affiliated_site",
}


SITE_TABLE_BASE = {
    SiteAction.CREATE: "allowed_to_create",
}


SITE_TABLE_UNAFFILIATED = {
    SiteAction.UPDATE_SETTINGS: "allowed_to_manage_unaffiliated_site",
    SiteAction.ENTER_DATA: "allowed_to_manage_unaffiliated_site",
    SiteAction.DELETE: "allowed_to_manage_unaffiliated_site",
    SiteAction.CREATE_NOTE: "allowed_to_manage_unaffiliated_site",
    SiteAction.EDIT_NOTE: "allowed_to_manage_unaffiliated_site",
    SiteAction.DELETE_NOTE: "allowed_to_manage_unaffiliated_site",
    SiteAction.UPDATE_DEPTH_INTERVAL: "allowed_to_manage_unaffiliated_site",
}


SITE_TABLE_AFFILIATED = {
    SiteAction.UPDATE_SETTINGS: "allowed_to_manage_project",
    SiteAction.ENTER_DATA: "allowed_to_contribute_to_affiliated_site",
    SiteAction.DELETE: "allowed_to_manage_project",
    SiteAction.CREATE_NOTE: "allowed_to_contribute_to_affiliated_site",
    SiteAction.EDIT_NOTE: "allowed_to_edit_affiliated_site_note",
    SiteAction.DELETE_NOTE: "allowed_to_delete_affiliated_site_note",
    SiteAction.UPDATE_DEPTH_INTERVAL: "allowed_to_contribute_to_affiliated_site",
}


def check_site_permission(user: User, action: SiteAction, context: Context) -> bool:
    if not context.site:
        table = SITE_TABLE_BASE
    elif context.site.is_unaffiliated:
        table = SITE_TABLE_UNAFFILIATED
    else:
        table = SITE_TABLE_AFFILIATED

    permission = get_table_permission(action, table)
    return user.has_perm(permission, context)


def check_project_permission(user: User, action: ProjectAction, context: Context) -> bool:
    # no attribute-dependent permission choices here yet, but the method is written this way to
    # have an api consistent with sites permissions
    permission = get_table_permission(action, PROJECT_TABLE)
    return user.has_perm(permission, context)


def get_table_permission(action: Enum, table: dict[Enum, str]) -> bool:
    if (result := table.get(action)) is None:
        raise KeyError(f"Unrecognized permission in this context: '{action}'")
    return result
