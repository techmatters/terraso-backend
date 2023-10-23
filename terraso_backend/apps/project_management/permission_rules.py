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

from .collaboration_roles import ROLE_MANAGER


@rules.predicate
def allowed_to_change_project(user, project):
    return project.is_manager(user)


@rules.predicate
def allowed_to_add_site_to_project(user, project):
    return project.is_manager(user) or project.is_contributor(user)


@rules.predicate
def allowed_to_update_site(user, site):
    if site.owned_by_user:
        return site.owner == user
    return site.project.is_manager(user)


@rules.predicate
def allowed_to_delete_site(user, site):
    return allowed_to_update_site(user, site)


@rules.predicate
def allowed_to_delete_project(user, project):
    return project.is_manager(user)


@rules.predicate
def allowed_to_add_to_project(user, project):
    return project.is_manager(user)


@rules.predicate
def allowed_to_archive_project(user, project):
    return project.is_manager(user)


@rules.predicate
def allowed_to_add_member_to_project(user, context):
    project = context["project"]
    requester_membership = context["requester_membership"]
    return (
        requester_membership.membership_list == project.membership_list
        and requester_membership.user_role == ROLE_MANAGER
    )


rules.add_rule("allowed_to_add_member_to_project", allowed_to_add_member_to_project)


@rules.predicate
def allowed_to_delete_user_from_project(user, context):
    project = context["project"]
    requester_membership = context["requester_membership"]
    target_membership = context["target_membership"]
    return project.membership_list == requester_membership.membership_list and (
        user == target_membership.user or requester_membership.user_role == ROLE_MANAGER
    )


rules.add_rule("allowed_to_delete_user_from_project", allowed_to_delete_user_from_project)


@rules.predicate
def allowed_to_change_user_project_role(user, context):
    project = context["project"]
    requester_membership = context["requester_membership"]
    target_membership = context["target_membership"]
    return (
        project.membership_list
        == requester_membership.membership_list
        == target_membership.membership_list
        and requester_membership.user_role == ROLE_MANAGER
    )


rules.add_rule("allowed_to_change_user_project_role", allowed_to_change_user_project_role)


@rules.predicate
def allowed_to_transfer_site_to_project(user, context):
    project, site = context
    # contributor can add user-owned site to project
    if site.owned_by_user:
        return (
            project.is_manager(user) or project.is_contributor(user)
        ) and site.owner.id == user.id
    return project.is_manager(user) and site.project.is_manager(user)


rules.add_rule("allowed_to_transfer_site_to_project", allowed_to_transfer_site_to_project)
