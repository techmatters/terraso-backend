# Copyright © 2021-2025 Technology Matters
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
def can_create_user_export_token(user, resource_id):
    """User can only create export tokens for themselves."""
    if user.is_anonymous:
        return False
    return str(user.id) == resource_id


@rules.predicate
def can_create_project_export_token(user, project):
    """Any project member can create an export token for the project."""
    if user.is_anonymous:
        return False
    return project.membership_list.memberships.filter(
        user=user,
        deleted_at__isnull=True,
    ).exists()


@rules.predicate
def can_create_site_export_token(user, site):
    """Site owner or any project member can create an export token for the site."""
    if user.is_anonymous:
        return False

    # Check if user owns the site directly (unaffiliated site)
    if site.owner == user:
        return True

    # Check if user is a member of site's project
    if site.project:
        return site.project.membership_list.memberships.filter(
            user=user,
            deleted_at__isnull=True,
        ).exists()

    return False


@rules.predicate
def owns_export_token(user, token):
    """User owns this export token (for view/delete operations)."""
    if user.is_anonymous:
        return False
    return str(user.id) == token.user_id


rules.add_perm("export.create_user_token", can_create_user_export_token)
rules.add_perm("export.create_project_token", can_create_project_export_token)
rules.add_perm("export.create_site_token", can_create_site_export_token)
rules.add_perm("export.owns_token", owns_export_token)
