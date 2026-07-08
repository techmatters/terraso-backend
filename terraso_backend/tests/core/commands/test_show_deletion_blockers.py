# Copyright © 2026 Technology Matters
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

"""Tests for the show_deletion_blockers management command.

Split into two layers:

  * Unit tests of `deletion_blockers()` — one per kind of blocker
    (PROTECT FKs across apps + the non-project APPROVED
    collaboration.Membership policy override, plus negative cases:
    pending/project memberships don't block, soft-deleted referencers
    don't block, LandPKS-cascade rows don't block).

  * End-to-end tests of the command — user lookup by email/ID, error
    paths, output format (empty case, populated case, truncation).
"""

from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from mixer.backend.django import mixer

from apps.collaboration.models import Membership as CollaborationMembership
from apps.core.management.commands.show_deletion_blockers import (
    BLOCKER_ID_CAP,
    deletion_blockers,
)
from apps.core.models import Group, Landscape, TaxonomyTerm, User
from apps.project_management.models import Project
from apps.shared_data.models import DataEntry, VisualizationConfig
from apps.story_map.models import StoryMap

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# deletion_blockers() — coverage for each kind of undeletable data
# ---------------------------------------------------------------------------


def _blocker_models(blockers):
    return {b["model"] for b in blockers}


def test_empty_for_brand_new_user():
    user = mixer.blend(User)
    assert deletion_blockers(user) == []


def test_dataentry_created_by_blocks():
    """DataEntry.created_by is PROTECT — must auto-block."""
    user = mixer.blend(User)
    mixer.blend(DataEntry, created_by=user)
    assert "shared_data.DataEntry" in _blocker_models(deletion_blockers(user))


def test_visualization_config_blocks():
    """VisualizationConfig.created_by is PROTECT — auto-block."""
    user = mixer.blend(User)
    mixer.blend(VisualizationConfig, created_by=user)
    assert "shared_data.VisualizationConfig" in _blocker_models(deletion_blockers(user))


def test_story_map_blocks():
    """StoryMap.created_by is PROTECT — auto-block."""
    user = mixer.blend(User)
    mixer.blend(StoryMap, created_by=user)
    assert "story_map.StoryMap" in _blocker_models(deletion_blockers(user))


def test_group_created_by_blocks():
    user = mixer.blend(User)
    mixer.blend(Group, created_by=user)
    assert "core.Group" in _blocker_models(deletion_blockers(user))


def test_landscape_created_by_blocks():
    user = mixer.blend(User)
    mixer.blend(Landscape, created_by=user)
    assert "core.Landscape" in _blocker_models(deletion_blockers(user))


def test_taxonomy_term_created_by_blocks():
    user = mixer.blend(User)
    mixer.blend(TaxonomyTerm, created_by=user)
    assert "core.TaxonomyTerm" in _blocker_models(deletion_blockers(user))


def test_non_project_approved_membership_blocks():
    """Policy override: a non-project APPROVED Membership blocks even
    though Membership.user is CASCADE."""
    user = mixer.blend(User)
    landscape = mixer.blend(Landscape)
    CollaborationMembership.objects.create(
        membership_list=landscape.membership_list,
        user=user,
        user_role="MEMBER",
        membership_status=CollaborationMembership.APPROVED,
    )
    assert any("Membership" in b["model"] for b in deletion_blockers(user))


def test_pending_membership_does_not_block():
    """Pending invites are CASCADE-safe; only APPROVED counts."""
    user = mixer.blend(User)
    landscape = mixer.blend(Landscape)
    CollaborationMembership.objects.create(
        membership_list=landscape.membership_list,
        user=user,
        user_role="MEMBER",
        membership_status=CollaborationMembership.PENDING,
    )
    assert not any("Membership" in b["model"] for b in deletion_blockers(user))


def test_project_membership_does_not_block():
    """Project memberships are torn down by the cascade — not blockers."""
    user = mixer.blend(User)
    project = mixer.blend(Project)
    project.add_manager(user)
    assert not any("Membership" in b["model"] for b in deletion_blockers(user))


def test_soft_deleted_blocker_does_not_block():
    """Soft-deleted rows no longer block: the resilient harddelete cron
    handles a not-yet-purged row in subsequent runs."""
    user = mixer.blend(User)
    story_map = mixer.blend(StoryMap, created_by=user)
    story_map.delete()
    assert not any(b["model"] == "story_map.StoryMap" for b in deletion_blockers(user))


def test_landpks_only_user_has_no_blockers():
    """LandPKS-cascade rows (Sites, soil data) don't appear as blockers —
    they cascade with the user via safedelete's SOFT_DELETE_CASCADE. The
    collector reaches them but they're not in `.protected`, so nothing
    surfaces."""
    from apps.project_management.models import Site
    from apps.project_management.models.site_notes import SiteNote

    user = mixer.blend(User)
    site = Site.objects.create(
        name="unaffiliated", latitude=0, longitude=0, elevation=0, owner=user
    )
    SiteNote.objects.create(site=site, content="note", author=user)
    assert deletion_blockers(user) == []


def test_ids_truncated_at_cap():
    """Blocker `ids` list is capped at BLOCKER_ID_CAP; `count` remains
    the true total so a caller can render '+N more'."""
    user = mixer.blend(User)
    for _ in range(BLOCKER_ID_CAP + 3):
        mixer.blend(DataEntry, created_by=user)
    [b] = [b for b in deletion_blockers(user) if b["model"] == "shared_data.DataEntry"]
    assert b["count"] == BLOCKER_ID_CAP + 3
    assert len(b["ids"]) == BLOCKER_ID_CAP


# ---------------------------------------------------------------------------
# End-to-end command tests
# ---------------------------------------------------------------------------


def _run_command(*args):
    out = StringIO()
    call_command("show_deletion_blockers", *args, stdout=out)
    return out.getvalue()


def test_command_empty_case_shows_no_blockers_message():
    user = mixer.blend(User, email="clean@example.com")
    output = _run_command(user.email)
    assert "No deletion blockers for 'clean@example.com'" in output


def test_command_lists_blockers_with_ids_and_labels():
    user = mixer.blend(User, email="blocked@example.com")
    entry = mixer.blend(DataEntry, created_by=user)
    output = _run_command(user.email)
    assert "Deletion blockers for 'blocked@example.com'" in output
    assert "shared_data.DataEntry (created_by)" in output
    assert str(entry.pk) in output


def test_command_shows_qualifier_for_membership_policy_override():
    user = mixer.blend(User)
    landscape = mixer.blend(Landscape)
    CollaborationMembership.objects.create(
        membership_list=landscape.membership_list,
        user=user,
        user_role="MEMBER",
        membership_status=CollaborationMembership.APPROVED,
    )
    output = _run_command(user.email)
    assert "collaboration.Membership (non-project, approved) (user)" in output


def test_command_accepts_user_id():
    user = mixer.blend(User)
    mixer.blend(DataEntry, created_by=user)
    output = _run_command(str(user.id))
    assert "shared_data.DataEntry" in output


def test_command_errors_on_missing_email():
    with pytest.raises(CommandError, match="No user with email"):
        _run_command("nobody@example.com")


def test_command_errors_on_missing_id():
    with pytest.raises(CommandError, match="No user with ID"):
        _run_command("00000000-0000-0000-0000-000000000001")


def test_command_errors_on_invalid_id():
    with pytest.raises(CommandError, match="No user with ID"):
        _run_command("not-a-uuid")


def test_command_shows_truncation_notice_when_over_cap():
    user = mixer.blend(User)
    for _ in range(BLOCKER_ID_CAP + 3):
        mixer.blend(DataEntry, created_by=user)
    output = _run_command(user.email)
    assert f"first {BLOCKER_ID_CAP} IDs" in output
    assert "(+3 more)" in output
