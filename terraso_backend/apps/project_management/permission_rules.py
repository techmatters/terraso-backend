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
from collections import namedtuple

import rules

# context data for a site-project management action
Context = namedtuple("Context", ["site", "project"])


@rules.predicate
def allowed_to_create(user, context):
    # (all logged-in users are allowed to create)
    return True


@rules.predicate
def allowed_to_manage_project(user, project):
    return project.is_manager(user)


@rules.predicate
def allowed_to_be_project_member(user, project):
    return project.is_manager(user) or project.is_contributor(user) or project.is_viewer(user)


@rules.predicate
def allowed_to_contribute_to_affiliated_site(user, site):
    if site.is_unaffiliated:
        return False
    return site.project.is_manager(user) or site.project.is_contributor(user)


@rules.predicate
def allowed_to_edit_affiliated_site_note(user, site_note):
    site = site_note.site
    if site.is_unaffiliated:
        return False
    return site.project.is_contributor(user) and site_note.is_author(user)


@rules.predicate
def allowed_to_delete_affiliated_site_note(user, site_note):
    site = site_note.site
    if site.is_unaffiliated:
        return False
    return site.project.is_manager(user) or (
        site.project.is_contributor(user) and site_note.is_author(user)
    )


@rules.predicate
def allowed_to_manage_unaffiliated_site(user, site):
    return site.is_unaffiliated and site.owner == user


@rules.predicate
def allowed_to_add_new_site_to_project(user, project):
    return project.is_manager(user) or project.is_contributor(user)


@rules.predicate
def allowed_to_add_unaffiliated_site_to_project(user, context):
    site = context.site
    project = context.project
    if not site.is_unaffiliated:
        return False
    return site.owner == user and (project.is_manager(user) or project.is_contributor(user))


@rules.predicate
def allowed_to_transfer_affiliated_site(user, context):
    site = context.site
    if site.is_unaffiliated:
        return False
    dest_project = context.project
    src_project = site.project
    return src_project.is_manager(user) and (
        dest_project is None or dest_project.is_manager(user) or dest_project.is_contributor(user)
    )
