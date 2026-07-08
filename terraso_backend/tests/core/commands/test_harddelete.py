# Copyright © 2023 Technology Matters
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

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.management import call_command
from mixer.backend.django import mixer

from apps.collaboration.models import Membership, MembershipList
from apps.core.management.commands.harddelete import Command
from apps.core.models import Group, Landscape, TaxonomyTerm, User
from apps.project_management.models import Project, Site
from apps.shared_data.models import DataEntry, VisualizationConfig
from apps.story_map.models import StoryMap

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("model", [User, Group, DataEntry])
def test_delete_model_deleted(model, delete_date):
    obj = mixer.blend(model)
    obj.delete()
    obj.deleted_at = delete_date
    obj.save(keep_deleted=True)
    call_command("harddelete")
    assert not model.objects.all(force_visibility=True).filter(id=obj.id).exists(), (
        "Model should be deleted"
    )


@pytest.mark.parametrize("model", [User, Group, DataEntry])
def test_delete_model_not_deleted(model, no_delete_date):
    obj = mixer.blend(model)
    obj.delete()
    obj.deleted_at = no_delete_date
    obj.save(keep_deleted=True)
    call_command("harddelete")
    assert model.objects.all(force_visibility=True).filter(id=obj.id).exists(), (
        "Model should not be deleted"
    )


# ---------------------------------------------------------------------------
# Resilience: one row's failure must not abort the batch
#
# Most in-tree models share SafeDelete's SOFT_DELETE_CASCADE policy, which
# means a hard-delete on a SafeDeleteModel naturally cascades to its
# SafeDelete-managed referencers — no integrity error fires for those.
# These tests therefore simulate the failure mode via patch, locking in
# the cron's defensive-hygiene contract for the rarer cases where it
# DOES matter (third-party models, non-SafeDelete referrers, buggy
# signals, etc.).
# ---------------------------------------------------------------------------


def _set_deleted_at(obj, when):
    """Back-date a soft-deleted row's deleted_at."""
    obj.deleted_at = when
    obj.save(keep_deleted=True)


def _soft_delete_at(obj, when):
    """Soft-delete and back-date in one step."""
    obj.delete()
    _set_deleted_at(obj, when)


def test_one_rows_exception_does_not_abort_batch(delete_date):
    """A simulated exception during one row's hard-delete (could be
    IntegrityError, RuntimeError from a signal handler, anything) is
    isolated. The other rows in the batch still get purged."""
    one = mixer.blend(Group)
    two = mixer.blend(Group)
    _soft_delete_at(one, delete_date)
    _soft_delete_at(two, delete_date)

    real_delete = Group.delete

    def selective_delete(self, *args, **kwargs):
        if self.id == one.id:
            raise RuntimeError("simulated failure")
        return real_delete(self, *args, **kwargs)

    with patch.object(Group, "delete", selective_delete):
        call_command("harddelete")

    # The exploding row stays; the other was purged.
    assert Group.objects.all(force_visibility=True).filter(id=one.id).exists()
    assert not Group.objects.all(force_visibility=True).filter(id=two.id).exists()


def test_failed_row_is_logged_with_model_and_pk(delete_date):
    """Each failed hard-delete emits a structured log line identifying
    the row (model label + pk) and the exception, so operators can
    triage without re-running the cron."""
    obj = mixer.blend(Group)
    _soft_delete_at(obj, delete_date)

    def always_fail(self, *args, **kwargs):
        raise RuntimeError("simulated failure")

    with (
        patch.object(Group, "delete", always_fail),
        patch("apps.core.management.commands.harddelete.logger") as mock_logger,
    ):
        call_command("harddelete")

    mock_logger.error.assert_any_call(
        "harddelete.row_failed",
        model="core.Group",
        pk=str(obj.id),
        error="simulated failure",
        error_type="RuntimeError",
    )


def test_retry_next_run_succeeds_after_transient_failure(delete_date):
    """Daily-retry convergence: a row that failed on one run is picked up
    by the next run and succeeds when the underlying condition (e.g. a
    blocking dependency was purged in the meantime) is resolved.

    Simulated by failing one row's delete on the first call, succeeding
    on the second."""
    obj = mixer.blend(Group)
    _soft_delete_at(obj, delete_date)

    real_delete = Group.delete
    call_count = {"n": 0}

    def fail_first_then_succeed(self, *args, **kwargs):
        if self.id == obj.id and call_count["n"] == 0:
            call_count["n"] += 1
            raise RuntimeError("transient failure")
        return real_delete(self, *args, **kwargs)

    with patch.object(Group, "delete", fail_first_then_succeed):
        call_command("harddelete")  # Run 1: fails on obj.
        assert Group.objects.all(force_visibility=True).filter(id=obj.id).exists()

        call_command("harddelete")  # Run 2: succeeds.
        assert not Group.objects.all(force_visibility=True).filter(id=obj.id).exists()


def test_empty_queue_runs_without_error():
    """No rows past the cutoff — cron exits cleanly, doesn't error on
    empty iteration."""
    call_command("harddelete")  # nothing to do, must not raise


def test_all_objects_sorted_by_deleted_at(delete_date):
    """Sort order is part of the contract — locks in that the dependency-
    ordering optimization isn't accidentally dropped."""
    older = mixer.blend(Group)
    newer = mixer.blend(Group)
    _soft_delete_at(older, delete_date - timedelta(hours=2))
    _soft_delete_at(newer, delete_date)

    objs = Command.all_objects(delete_date + timedelta(hours=1))
    timestamps = [o.deleted_at for o in objs]
    assert timestamps == sorted(timestamps)


# ---------------------------------------------------------------------------
# Cascade / convergence verification across all 6 User-blocker models.
#
# All 6 blocker models now use PROTECT (DataEntry.created_by and
# StoryMap.created_by were migrated from DO_NOTHING to PROTECT so
# safedelete's collector raises them consistently). User hard-delete
# raises ProtectedError when the referencer still exists; the cron's
# try/except + sort + daily retry converges over at most 2 runs:
# run 1 succeeds purging the blocker, fails on the user; run 2 picks
# up the user (no references left) and succeeds.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "blocker_model",
    [Group, Landscape, TaxonomyTerm, DataEntry, VisualizationConfig, StoryMap],
)
def test_cron_converges_within_two_runs(blocker_model, delete_date):
    """For each of the 6 User-blocker models: soft-delete the referencer
    first (gate allows it), then the user. After at most 2 cron runs,
    both are gone. All 6 blocker models are PROTECT, so 2 runs are
    needed for each."""
    user = mixer.blend(User)
    blocker = mixer.blend(blocker_model, created_by=user)
    blocker.delete()  # soft-delete referencer first so the gate allows user.delete
    user.delete()
    _set_deleted_at(blocker, delete_date)
    _set_deleted_at(user, delete_date)

    call_command("harddelete")
    call_command("harddelete")

    assert not blocker_model.objects.all(force_visibility=True).filter(id=blocker.id).exists()
    assert not User.objects.all(force_visibility=True).filter(id=user.id).exists()


def test_cron_cleans_up_solo_manager_project_cascade(delete_date):
    """User → solo-manager Project triggers an explicit cascade in
    `User._soft_delete_with_cascade` (soft-deletes the Project) and
    `Project.soft_delete_policy_action` (soft-deletes the MembershipList).
    After soft-delete: User, Project, MembershipList, Membership, Site
    all carry deleted_at. The cron must purge all of them without
    leaving any dangling rows."""
    user = mixer.blend(User)
    project = mixer.blend(Project)
    project.add_manager(user)
    site = mixer.blend(Site, project=project)
    membership_list = project.membership_list
    membership = Membership.objects.get(membership_list=membership_list, user=user)

    user.delete()  # cascade soft-deletes Project, MembershipList, Membership, Site
    project.refresh_from_db()
    assert project.deleted_at is not None  # sanity check
    _set_deleted_at(user, delete_date)
    _set_deleted_at(project, delete_date)
    _set_deleted_at(membership_list, delete_date)
    _set_deleted_at(membership, delete_date)
    _set_deleted_at(site, delete_date)

    call_command("harddelete")

    assert not User.objects.all(force_visibility=True).filter(id=user.id).exists()
    assert not Project.objects.all(force_visibility=True).filter(id=project.id).exists()
    assert (
        not MembershipList.objects.all(force_visibility=True).filter(id=membership_list.id).exists()
    )
    assert not Membership.objects.all(force_visibility=True).filter(id=membership.id).exists()
    assert not Site.objects.all(force_visibility=True).filter(id=site.id).exists()


def test_cron_preserves_co_managed_project(delete_date, user, user_b):
    """User soft-delete on a co-managed Project should leave the Project
    AND the co-manager's Membership intact. After cron: User and their
    own Membership are gone; Project and user_b's Membership survive."""
    project = mixer.blend(Project)
    project.add_manager(user)
    project.add_manager(user_b)
    user_membership = Membership.objects.get(membership_list=project.membership_list, user=user)
    user_b_membership = Membership.objects.get(membership_list=project.membership_list, user=user_b)

    user.delete()  # soft-delete; project survives (has a co-manager)
    project.refresh_from_db()
    assert project.deleted_at is None  # sanity check — project survives soft-delete
    _set_deleted_at(user, delete_date)
    _set_deleted_at(user_membership, delete_date)

    call_command("harddelete")

    # User and their membership purged.
    assert not User.objects.all(force_visibility=True).filter(id=user.id).exists()
    assert not Membership.objects.all(force_visibility=True).filter(id=user_membership.id).exists()
    # Project + co-manager's membership preserved.
    assert Project.objects.filter(id=project.id).exists()
    assert Membership.objects.filter(id=user_b_membership.id).exists()


def test_cron_purges_directly_soft_deleted_project(delete_date):
    """Project soft-delete (not via user cascade) triggers
    `Project.soft_delete_policy_action` which soft-deletes the
    MembershipList. The cron should purge both cleanly."""
    project = mixer.blend(Project)
    membership_list = project.membership_list

    project.delete()  # triggers policy_action cleanup of membership_list
    membership_list.refresh_from_db()
    assert membership_list.deleted_at is not None  # sanity check
    _set_deleted_at(project, delete_date)
    _set_deleted_at(membership_list, delete_date)

    call_command("harddelete")

    assert not Project.objects.all(force_visibility=True).filter(id=project.id).exists()
    assert (
        not MembershipList.objects.all(force_visibility=True).filter(id=membership_list.id).exists()
    )
