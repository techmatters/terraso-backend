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

import pytest
from mixer.backend.django import mixer

from apps.project_management import permission_rules
from apps.project_management.models import Project, Site, SiteNote

pytestmark = pytest.mark.django_db


def test_user_can_create(user):
    assert permission_rules.allowed_to_create(user, None) is True


def test_project_manager_can_manage_project(project, project_manager):
    assert permission_rules.allowed_to_manage_project(project_manager, project) is True


def test_project_manager_cant_manage_other_project(project_manager):
    project_b = mixer.blend(Project)
    assert permission_rules.allowed_to_manage_project(project_manager, project_b) is False


def test_project_non_manager_cant_manage_project(user, project):
    assert permission_rules.allowed_to_manage_project(user, project) is False


def test_project_manager_can_be_member(project, user):
    project.add_manager(user)
    assert permission_rules.allowed_to_be_project_member(user, project) is True


def test_project_contributor_can_be_member(project, user):
    project.add_contributor(user)
    assert permission_rules.allowed_to_be_project_member(user, project) is True


def test_project_viewer_can_be_member(project, user):
    project.add_viewer(user)
    assert permission_rules.allowed_to_be_project_member(user, project) is True


def test_other_user_cant_be_member(project, user):
    assert permission_rules.allowed_to_be_project_member(user, project) is False


def test_cant_contribute_to_unaffiliated_affiliated_site(site, site_creator):
    assert permission_rules.allowed_to_contribute_to_affiliated_site(site_creator, site) is False


def test_project_manager_can_contribute_to_affiliated_site(project_site, project_manager):
    assert (
        permission_rules.allowed_to_contribute_to_affiliated_site(project_manager, project_site)
        is True
    )


def test_project_contributor_can_contribute_to_affiliated_site(project, project_site, user):
    project.add_contributor(user)
    assert permission_rules.allowed_to_contribute_to_affiliated_site(user, project_site) is True


def test_project_viewer_cant_contribute_to_affiliated_site(project, project_site, user):
    project.add_viewer(user)
    assert permission_rules.allowed_to_contribute_to_affiliated_site(user, project_site) is False


def test_other_project_users_cant_contribute_to_affiliated_site(project_manager):
    project_b = mixer.blend(Project)
    site = mixer.blend(Site, project=project_b)
    assert permission_rules.allowed_to_contribute_to_affiliated_site(project_manager, site) is False


def test_contributing_note_author_can_edit_affiliated_note(user, project, project_site):
    project.add_contributor(user)
    site_note = mixer.blend(SiteNote, author=user, site=project_site)
    assert permission_rules.allowed_to_edit_affiliated_site_note(user, site_note) is True


def test_non_contributing_note_author_cant_edit_affiliated_note(user, project_site):
    site_note = mixer.blend(SiteNote, author=user, site=project_site)
    assert permission_rules.allowed_to_edit_affiliated_site_note(user, site_note) is False


def test_contributing_non_note_author_cant_edit_affiliated_note(
    user, user_b, project, project_site
):
    project.add_contributor(user)
    site_note = mixer.blend(SiteNote, author=user_b, site=project_site)
    assert permission_rules.allowed_to_edit_affiliated_site_note(user, site_note) is False


def test_contributing_note_author_can_delete_affiliated_note(user, project, project_site):
    project.add_contributor(user)
    site_note = mixer.blend(SiteNote, author=user, site=project_site)
    assert permission_rules.allowed_to_delete_affiliated_site_note(user, site_note) is True


def test_non_contributing_note_author_cant_delete_affiliated_note(user, project_site):
    site_note = mixer.blend(SiteNote, author=user, site=project_site)
    assert permission_rules.allowed_to_delete_affiliated_site_note(user, site_note) is False


def test_contributing_non_note_author_cant_delete_affiliated_note(
    user, user_b, project, project_site
):
    project.add_contributor(user)
    site_note = mixer.blend(SiteNote, author=user_b, site=project_site)
    assert permission_rules.allowed_to_delete_affiliated_site_note(user, site_note) is False


def test_manager_can_delete_affiliated_note(user, project_site, project_manager):
    site_note = mixer.blend(SiteNote, author=user, site=project_site)
    assert (
        permission_rules.allowed_to_delete_affiliated_site_note(project_manager, site_note) is True
    )


def test_cant_edit_unaffiliated_site_note(user, site):
    site_note = mixer.blend(SiteNote, author=user, site=site)
    assert permission_rules.allowed_to_edit_affiliated_site_note(user, site_note) is False


def test_site_owner_can_manage_unaffiliated_site(user, site):
    assert permission_rules.allowed_to_manage_unaffiliated_site(user, site) is True


def test_site_non_owner_cant_manage_unaffiliated_site(user_b, site):
    assert permission_rules.allowed_to_manage_unaffiliated_site(user_b, site) is False


def test_cant_manage_affiliated_site(user, project_site):
    assert permission_rules.allowed_to_manage_unaffiliated_site(user, project_site) is False


def test_contributor_site_owner_can_add_unaffiliated_site(user, site, project):
    project.add_contributor(user)
    context = {"site": site, "project": project}
    assert permission_rules.allowed_to_add_unaffiliated_site_to_project(user, context) is True


def test_manager_site_owner_can_add_unaffiliated_site(user, site, project):
    project.add_manager(user)
    context = {"site": site, "project": project}
    assert permission_rules.allowed_to_add_unaffiliated_site_to_project(user, context) is True


def test_manager_non_site_owner_cant_add_unaffiliated_site(project_manager, site, project):
    context = {"site": site, "project": project}
    assert (
        permission_rules.allowed_to_add_unaffiliated_site_to_project(project_manager, context)
        is False
    )


def test_cant_add_affiliated_site(site, project, project_manager):
    project_b = mixer.blend(Project)
    site = mixer.blend(Site, project=project_b)
    context = {"site": site, "project": project}
    assert (
        permission_rules.allowed_to_add_unaffiliated_site_to_project(project_manager, context)
        is False
    )


def test_src_manager_dest_manager_can_transfer_affiliated_site(user, project_site, project):
    project.add_manager(user)
    project_b = mixer.blend(Project)
    project_b.add_manager(user)
    context = {"site": project_site, "project": project_b}
    assert permission_rules.allowed_to_transfer_affiliated_site(user, context) is True


def test_src_manager_dest_contributor_can_transfer_affiliated_site(user, project_site, project):
    project.add_manager(user)
    project_b = mixer.blend(Project)
    project_b.add_contributor(user)
    context = {"site": project_site, "project": project_b}
    assert permission_rules.allowed_to_transfer_affiliated_site(user, context) is True


def test_src_manager_can_transfer_affiliated_site_to_none(user, project_site, project):
    project.add_manager(user)
    context = {"site": project_site, "project": None}
    assert permission_rules.allowed_to_transfer_affiliated_site(user, context) is True


def test_src_non_manager_cant_transfer_affiliated_site(user, project_site, project):
    project.add_contributor(user)
    project_b = mixer.blend(Project)
    project_b.add_contributor(user)
    context = {"site": project_site, "project": project_b}
    assert permission_rules.allowed_to_transfer_affiliated_site(user, context) is False


def test_dst_non_manager_or_contributor_cant_transfer_affiliated_site(user, project_site, project):
    project.add_manager(user)
    project_b = mixer.blend(Project)
    project_b.add_viewer(user)
    context = {"site": project_site, "project": project_b}
    assert permission_rules.allowed_to_transfer_affiliated_site(user, context) is False


def test_cant_transfer_unaffiliated_site(user, site):
    project_b = mixer.blend(Project)
    project_b.add_manager(user)
    context = {"site": site, "project": project_b}
    assert permission_rules.allowed_to_transfer_affiliated_site(user, context) is False
