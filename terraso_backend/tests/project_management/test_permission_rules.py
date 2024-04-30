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

import pytest
from mixer.backend.django import mixer

from apps.project_management.models import Project, Site, SiteNote
from apps.project_management.permission_rules import (
    Context,
    allowed_to_add_new_site_to_project,
    allowed_to_add_unaffiliated_site_to_project,
    allowed_to_contribute_to_affiliated_site,
    allowed_to_create,
    allowed_to_delete_affiliated_site_note,
    allowed_to_edit_affiliated_site_note,
    allowed_to_manage_project,
    allowed_to_manage_unaffiliated_site,
    allowed_to_transfer_affiliated_site,
    is_project_member,
)

pytestmark = pytest.mark.django_db


def test_user_can_create(user):
    assert allowed_to_create(user, None) is True


def test_project_manager_can_manage_project(project, project_manager):
    assert allowed_to_manage_project(project_manager, Context(project=project)) is True


def test_project_manager_cant_manage_other_project(project_manager):
    project_b = mixer.blend(Project)
    assert allowed_to_manage_project(project_manager, Context(project=project_b)) is False


def test_project_non_manager_cant_manage_project(user, project):
    assert allowed_to_manage_project(user, Context(project=project)) is False


def test_project_manager_can_be_member(project, user):
    project.add_manager(user)
    assert is_project_member(user, Context(project=project)) is True


def test_project_contributor_can_be_member(project, user):
    project.add_contributor(user)
    assert is_project_member(user, Context(project=project)) is True


def test_project_viewer_can_be_member(project, user):
    project.add_viewer(user)
    assert is_project_member(user, Context(project=project)) is True


def test_other_user_cant_be_member(project, user):
    assert is_project_member(user, Context(project=project)) is False


def test_cant_contribute_to_unaffiliated_site(site, site_creator):
    with pytest.raises(ValueError):
        allowed_to_contribute_to_affiliated_site(site_creator, Context(site=site))


def test_project_manager_can_contribute_to_affiliated_site(project_site, project_manager):
    assert (
        allowed_to_contribute_to_affiliated_site(project_manager, Context(site=project_site))
        is True
    )


def test_project_contributor_can_contribute_to_affiliated_site(project, project_site, user):
    project.add_contributor(user)
    assert allowed_to_contribute_to_affiliated_site(user, Context(site=project_site)) is True


def test_project_viewer_cant_contribute_to_affiliated_site(project, project_site, user):
    project.add_viewer(user)
    assert allowed_to_contribute_to_affiliated_site(user, Context(site=project_site)) is False


def test_other_project_users_cant_contribute_to_affiliated_site(project_manager):
    project_b = mixer.blend(Project)
    site = mixer.blend(Site, project=project_b)
    assert allowed_to_contribute_to_affiliated_site(project_manager, Context(site=site)) is False


def test_contributing_note_author_can_edit_affiliated_note(user, project, project_site):
    project.add_contributor(user)
    site_note = mixer.blend(SiteNote, author=user, site=project_site)
    assert allowed_to_edit_affiliated_site_note(user, Context(site_note=site_note)) is True


def test_manager_note_author_can_edit_affiliated_note(user, project, project_site):
    project.add_manager(user)
    site_note = mixer.blend(SiteNote, author=user, site=project_site)
    assert allowed_to_edit_affiliated_site_note(user, Context(site_note=site_note)) is True


def test_non_contributing_note_author_cant_edit_affiliated_note(user, project_site):
    site_note = mixer.blend(SiteNote, author=user, site=project_site)
    assert allowed_to_edit_affiliated_site_note(user, Context(site_note=site_note)) is False


def test_manager_non_note_author_cant_edit_affiliated_note(user, user_b, project, project_site):
    project.add_manager(user)
    site_note = mixer.blend(SiteNote, author=user_b, site=project_site)
    assert allowed_to_edit_affiliated_site_note(user, Context(site_note=site_note)) is False


def test_contributing_non_note_author_cant_edit_affiliated_note(
    user, user_b, project, project_site
):
    project.add_contributor(user)
    site_note = mixer.blend(SiteNote, author=user_b, site=project_site)
    assert allowed_to_edit_affiliated_site_note(user, Context(site_note=site_note)) is False


def test_cant_edit_unaffiliated_site_note(user, site):
    site_note = mixer.blend(SiteNote, author=user, site=site)
    with pytest.raises(ValueError):
        allowed_to_edit_affiliated_site_note(user, Context(site_note=site_note))


def test_contributing_note_author_can_delete_affiliated_note(user, project, project_site):
    project.add_contributor(user)
    site_note = mixer.blend(SiteNote, author=user, site=project_site)
    assert allowed_to_delete_affiliated_site_note(user, Context(site_note=site_note)) is True


def test_non_contributing_note_author_cant_delete_affiliated_note(user, project_site):
    site_note = mixer.blend(SiteNote, author=user, site=project_site)
    assert allowed_to_delete_affiliated_site_note(user, Context(site_note=site_note)) is False


def test_contributing_non_note_author_cant_delete_affiliated_note(
    user, user_b, project, project_site
):
    project.add_contributor(user)
    site_note = mixer.blend(SiteNote, author=user_b, site=project_site)
    assert allowed_to_delete_affiliated_site_note(user, Context(site_note=site_note)) is False


def test_manager_can_delete_affiliated_note(user, project_site, project_manager):
    site_note = mixer.blend(SiteNote, author=user, site=project_site)
    assert (
        allowed_to_delete_affiliated_site_note(project_manager, Context(site_note=site_note))
        is True
    )


def test_cant_deleteunaffiliated_site_note(user, site):
    site_note = mixer.blend(SiteNote, author=user, site=site)
    with pytest.raises(ValueError):
        allowed_to_delete_affiliated_site_note(user, Context(site_note=site_note))


def test_site_owner_can_manage_unaffiliated_site(user, site):
    assert allowed_to_manage_unaffiliated_site(user, Context(site=site)) is True


def test_site_non_owner_cant_manage_unaffiliated_site(user_b, site):
    assert allowed_to_manage_unaffiliated_site(user_b, Context(site=site)) is False


def test_cant_manage_affiliated_site(user, project_site):
    with pytest.raises(ValueError):
        allowed_to_manage_unaffiliated_site(user, Context(site=project_site))


def test_contributor_can_add_new_site(user, project):
    project.add_contributor(user)
    assert allowed_to_add_new_site_to_project(user, Context(project=project)) is True


def test_manager_can_add_new_site(user, project):
    project.add_manager(user)
    assert allowed_to_add_new_site_to_project(user, Context(project=project)) is True


def test_other_user_cant_add_new_site(user, project):
    assert allowed_to_add_new_site_to_project(user, Context(project=project)) is False


def test_contributor_site_owner_can_add_unaffiliated_site(user, site, project):
    project.add_contributor(user)
    assert (
        allowed_to_add_unaffiliated_site_to_project(
            user, Context(project=project, source_site=site)
        )
        is True
    )


def test_manager_site_owner_can_add_unaffiliated_site(user, site, project):
    project.add_manager(user)
    assert (
        allowed_to_add_unaffiliated_site_to_project(
            user, Context(project=project, source_site=site)
        )
        is True
    )


def test_manager_non_site_owner_cant_add_unaffiliated_site(project_manager, site, project):
    assert (
        allowed_to_add_unaffiliated_site_to_project(
            project_manager, Context(project=project, source_site=site)
        )
        is False
    )


def test_cant_add_affiliated_site(site, project, project_manager):
    project_b = mixer.blend(Project)
    site = mixer.blend(Site, project=project_b)
    with pytest.raises(ValueError):
        allowed_to_add_unaffiliated_site_to_project(
            project_manager, Context(project=project, source_site=site)
        )


def test_src_manager_dest_manager_can_transfer_affiliated_site(user, project_site, project):
    project.add_manager(user)
    project_b = mixer.blend(Project)
    project_b.add_manager(user)
    assert (
        allowed_to_transfer_affiliated_site(
            user, Context(project=project_b, source_site=project_site)
        )
        is True
    )


def test_src_manager_dest_contributor_can_transfer_affiliated_site(user, project_site, project):
    project.add_manager(user)
    project_b = mixer.blend(Project)
    project_b.add_contributor(user)
    assert (
        allowed_to_transfer_affiliated_site(
            user, Context(project=project_b, source_site=project_site)
        )
        is True
    )


def test_src_manager_can_transfer_affiliated_site_to_none(user, project_site, project):
    project.add_manager(user)
    assert (
        allowed_to_transfer_affiliated_site(user, Context(project=None, source_site=project_site))
        is True
    )


def test_src_non_manager_cant_transfer_affiliated_site(user, project_site, project):
    project.add_contributor(user)
    project_b = mixer.blend(Project)
    project_b.add_contributor(user)
    assert (
        allowed_to_transfer_affiliated_site(
            user, Context(project=project_b, source_site=project_site)
        )
        is False
    )


def test_dst_non_manager_or_contributor_cant_transfer_affiliated_site(user, project_site, project):
    project.add_manager(user)
    project_b = mixer.blend(Project)
    project_b.add_viewer(user)
    assert (
        allowed_to_transfer_affiliated_site(
            user, Context(project=project_b, source_site=project_site)
        )
        is False
    )


def test_cant_transfer_unaffiliated_site(user, site):
    project_b = mixer.blend(Project)
    project_b.add_manager(user)
    with pytest.raises(ValueError):
        allowed_to_transfer_affiliated_site(user, Context(project=project_b, source_site=site))
