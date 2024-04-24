# Copyright © 2021–2024 Technology Matters
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
from dataclasses import dataclass

import rules

from apps.project_management.models import Project, Site, SiteNote


@dataclass
class Context:
    # these are the target entity(s) the operation is occurring on. they will always be
    # referentually consistent (i.e., if the context has a site this will always be the site's
    # project)
    project: Project = None
    site: Site = None
    site_note: SiteNote = None

    # these are the source entities which may also be part of the operation (i.e., the site which
    # is being added to a new owner, and that site's current project if it has one)
    source_project: Project = None
    source_site: Site = None

    def __post_init__(self):
        if self.site_note:
            self.site = self.site_note.site
        if self.site:
            self.project = self.site.project
        if self.source_site:
            self.source_project = self.source_site.project


@rules.predicate
def allowed_to_create(user, context):
    # (all logged-in users are allowed base creation actions)
    return True


@rules.predicate
def allowed_to_manage_project(user, context):
    return context.project.is_manager(user)


@rules.predicate
def is_project_member(user, context):
    return (
        context.project.is_manager(user)
        or context.project.is_contributor(user)
        or context.project.is_viewer(user)
    )


@rules.predicate
def allowed_to_contribute_to_affiliated_site(user, context):
    if context.site.is_unaffiliated:
        return False
    return context.project.is_manager(user) or context.project.is_contributor(user)


@rules.predicate
def allowed_to_edit_affiliated_site_note(user, context):
    if context.site.is_unaffiliated:
        return False
    return context.project.is_contributor(user) and context.site_note.is_author(user)


@rules.predicate
def allowed_to_delete_affiliated_site_note(user, context):
    if context.site.is_unaffiliated:
        return False
    return context.project.is_manager(user) or (
        context.project.is_contributor(user) and context.site_note.is_author(user)
    )


@rules.predicate
def allowed_to_manage_unaffiliated_site(user, context):
    return context.site.is_unaffiliated and context.site.owner == user


@rules.predicate
def allowed_to_add_new_site_to_project(user, context):
    return context.project.is_manager(user) or context.project.is_contributor(user)


@rules.predicate
def allowed_to_add_unaffiliated_site_to_project(user, context):
    if not context.source_site.is_unaffiliated:
        return False
    return context.source_site.owner == user and (
        context.project.is_manager(user) or context.project.is_contributor(user)
    )


@rules.predicate
def allowed_to_transfer_affiliated_site(user, context):
    if context.source_site.is_unaffiliated:
        return False
    dest_project = context.project
    src_project = context.source_project
    return src_project.is_manager(user) and (
        dest_project is None or dest_project.is_manager(user) or dest_project.is_contributor(user)
    )


rules.add_perm("allowed_to_create", allowed_to_create)
rules.add_perm("allowed_to_manage_project", allowed_to_manage_project)
rules.add_perm("is_project_member", is_project_member)
rules.add_perm("allowed_to_contribute_to_affiliated_site", allowed_to_contribute_to_affiliated_site)
rules.add_perm("allowed_to_edit_affiliated_site_note", allowed_to_edit_affiliated_site_note)
rules.add_perm("allowed_to_delete_affiliated_site_note", allowed_to_delete_affiliated_site_note)
rules.add_perm("allowed_to_manage_unaffiliated_site", allowed_to_manage_unaffiliated_site)
rules.add_perm("allowed_to_add_new_site_to_project", allowed_to_add_new_site_to_project)
rules.add_perm(
    "allowed_to_add_unaffiliated_site_to_project", allowed_to_add_unaffiliated_site_to_project
)
rules.add_perm("allowed_to_transfer_affiliated_site", allowed_to_transfer_affiliated_site)
