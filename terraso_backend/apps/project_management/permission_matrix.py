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

PROJECT_PERMISSIONS = {
    "create": "allowed_to_create",
    "update_requirements": "allowed_to_manage_project",
    "edit_pinned_note": "allowed_to_manage_project",
    "archive": "allowed_to_manage_project",
    "add_member": "allowed_to_manage_project",
    "change_user_role": "allowed_to_manage_project",
    "delete_user": "allowed_to_manage_project",
    "delete": "allowed_to_manage_project",
    "generate_link": "allowed_to_manage_project",
    "change_required_depth_interval": "allowed_to_manage_project",
    "leave": "allowed_to_be_project_member",
    "add_new_site": "allowed_to_add_new_site_to_project",
    "add_unaffiliated_site": "allowed_to_add_unaffiliated_site_to_project",
    "transfer_affiliated_site": "allowed_to_transfer_affiliated_site",
}


SITE_PERMISSIONS_BASE = {
    "create": "allowed_to_create",
}


SITE_PERMISSIONS_UNAFFILIATED = {
    "update_settings": "allowed_to_manage_unaffiliated_site",
    "enter_data": "allowed_to_manage_unaffiliated_site",
    "delete": "allowed_to_manage_unaffiliated_site",
    "create_note": "allowed_to_manage_unaffiliated_site",
    "edit_note": "allowed_to_manage_unaffiliated_site",
    "delete_note": "allowed_to_manage_unaffiliated_site",
    "update_depth_interval": "allowed_to_manage_unaffiliated_site",
}


SITE_PERMISSIONS_AFFILIATED = {
    "update_settings": "allowed_to_manage_project",
    "enter_data": "allowed_to_contribute_to_affiliated_site",
    "delete": "allowed_to_manage_project",
    "create_note": "allowed_to_contribute_to_affiliated_site",
    "edit_note": "allowed_to_edit_affiliated_site_note",
    "delete_note": "allowed_to_delete_affiliated_site_note",
    "update_depth_interval": "allowed_to_contribute_to_affiliated_site",
}


def check_site_permission(user, name, context):

    if not context.site:
        matrix = SITE_PERMISSIONS_BASE
    elif context.site.is_unaffiliated:
        matrix = SITE_PERMISSIONS_UNAFFILIATED
    else:
        matrix = SITE_PERMISSIONS_AFFILIATED

    permission = get_matrix_permission(name, matrix)

    return user.has_perm(permission, context)


def check_project_permission(user, name, context):
    # no attribute-dependent permission choices here yet, but the method is written this way to
    # have an api consistent with sites permissions
    permission = get_matrix_permission(name, PROJECT_PERMISSIONS)
    return user.has_perm(permission, context)


def get_matrix_permission(name, matrix):
    if (result := matrix.get(name)) is None:
        raise KeyError(f"Unrecognized permission name in this context: '{name}'")
    return result
