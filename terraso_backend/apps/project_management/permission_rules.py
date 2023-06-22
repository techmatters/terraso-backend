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
def allowed_to_change_project(user, project):
    return project.is_manager(user)


@rules.predicate
def allowed_to_add_site_to_project(user, project):
    return project.is_manager(user) or (
        project.is_member(user) and project.settings.member_can_add_site_to_project
    )


@rules.predicate
def allowed_to_edit_site(user, site):
    if site.owned_by_user:
        return site.owner == user
    if site.project.is_manager(user):
        return True
    if site.project.is_member(user):
        return site.project.settings.member_can_edit_site
    return False


@rules.predicate
def allowed_to_delete_project(user, project):
    return project.is_manager(user)


@rules.predicate
def allowed_to_add_to_project(user, project):
    return project.is_manager(user)
