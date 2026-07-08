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

"""Tests for the User soft-delete gate.

Two layers under test here:

  * `User.delete()` — enforcement: raises `UserDeletionBlockedError` on
    the soft-delete path when blockers exist; does not fire on
    `force_policy=HARD_DELETE`.
  * `User.soft_delete_policy_action` / `Project.soft_delete_policy_action`
    — the cascade that tears down the user's landpks footprint and
    solo-manager projects.

Blocker enumeration (which rows count, per-model coverage) is tested in
`tests/core/commands/test_show_deletion_blockers.py`, since that logic
lives entirely in the diagnostic command now.

Plus structural tests that catch schema drift in CI:

  * **Classification test**: every reverse FK to User is classified into
    exactly one of the five legal buckets (LANDPKS app, system app,
    Membership special case, CASCADE/SET_NULL/SET, PROTECT/RESTRICT).
    Also asserts no DO_NOTHING FKs to User outside LANDPKS_APP_LABELS —
    new blockers must use PROTECT so safedelete's collector raises them.
  * **Closure test**: the transitive closure of models soft-deleted by
    `user.delete()` has no model referenced via a PROTECT/RESTRICT/
    DO_NOTHING FK from inside or outside the closure — proves the
    harddelete cron can purge the closure without crashing on a
    constraint."""

import pytest
from django.core.exceptions import ValidationError
from mixer.backend.django import mixer
from safedelete.models import HARD_DELETE

from apps.collaboration.models import Membership as CollaborationMembership
from apps.collaboration.models import MembershipList
from apps.core.models import Landscape, User
from apps.project_management.models import Project, Site
from apps.project_management.models.site_notes import SiteNote
from apps.shared_data.models import DataEntry
from tests.utils import add_soil_data_to_site

pytestmark = pytest.mark.django_db


# Schema-invariant constants used by the structural tests below.
# Kept in the test file (rather than in users.py) because after the
# collector-based show_deletion_blockers refactor no runtime code path
# reads them — only these tests do.

# Domain apps whose data cascades with the user (LandPKS subtree). New
# FKs to User from these apps are exempt from the "block-at-gate" rule
# because User._soft_delete_with_cascade / Project.soft_delete_policy_action
# tear their rows down explicitly. Add a new app_label here (and confirm
# the closure test still passes) when introducing a domain app whose
# data should cascade rather than block.
LANDPKS_APP_LABELS = {"project_management", "soil_id"}

# Django internals — reverse FKs to User in these apps are auto-allowed
# (Django manages them itself).
SYSTEM_APP_LABELS = {"admin", "auth", "contenttypes", "sessions"}

# on_delete behaviors that raise (via safedelete's collector or DB) when
# the referenced User is deleted, so a row pointing at the User through
# one of these FKs blocks deletion. DO_NOTHING is deliberately excluded —
# new FKs to User should use PROTECT instead (enforced by test A below).
BLOCKING_ON_DELETE = {"PROTECT", "RESTRICT"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def landpks_user():
    """A user whose only footprint is landpks data: an unaffiliated site
    with soil data + depth intervals + a note, plus a solo-manager
    project that also has sites + soil data + a note. Used to verify the
    cascade tears down the full nested tree."""
    user = mixer.blend(User)
    # Unaffiliated owned site.
    unaffiliated = Site.objects.create(
        name="unaffiliated", latitude=0, longitude=0, elevation=0, owner=user
    )
    SiteNote.objects.create(site=unaffiliated, content="own note", author=user)
    return user


# ---------------------------------------------------------------------------
# Structural Test A: every reverse FK to User is classified
# ---------------------------------------------------------------------------


def test_structural_every_user_fk_is_classified():
    """For every reverse FK to User, assert it falls into exactly one
    legal bucket AND that no new DO_NOTHING FKs are added outside
    LANDPKS_APP_LABELS. A future PR that adds an unhandled FK — or a
    DO_NOTHING FK that would silently pass safedelete's collector and
    crash the harddelete cron later — fails here."""
    unclassified = []
    do_nothing = []
    for rel in User._meta.related_objects:
        # M2M reverse relations are skipped (through-rows auto-clean).
        if rel.many_to_many:
            continue
        related_model = rel.related_model
        app = related_model._meta.app_label
        on_delete_name = rel.on_delete.__name__.upper()

        # DO_NOTHING is banned outside LANDPKS: safedelete's collector
        # won't raise for it, so the user would silently soft-delete and
        # the harddelete cron would crash on the dangling FK. Use PROTECT
        # instead so the gate refuses via the natural ProtectedError.
        if on_delete_name == "DO_NOTHING" and app not in LANDPKS_APP_LABELS:
            do_nothing.append(f"{related_model._meta.label}.{rel.field.name} — use PROTECT instead")

        bucket = None
        if app in LANDPKS_APP_LABELS:
            bucket = "landpks"
        elif app in SYSTEM_APP_LABELS:
            bucket = "system"
        elif related_model._meta.label == "collaboration.Membership":
            bucket = "membership-policy-override"
        else:
            if on_delete_name in BLOCKING_ON_DELETE:
                bucket = f"auto-block ({on_delete_name})"
            elif on_delete_name in {"CASCADE", "SET_NULL", "SET_DEFAULT", "SET"}:
                bucket = f"auto-allow ({on_delete_name})"

        if bucket is None:
            unclassified.append(
                f"{related_model._meta.label}.{rel.field.name} (on_delete={rel.on_delete.__name__})"
            )

    assert not unclassified, (
        "Unclassified reverse FK(s) to User — classify by adding the "
        "on_delete to BLOCKING_ON_DELETE (block-at-gate) or the "
        "CASCADING allowlist (auto-cascade), or by adding the app to "
        f"LANDPKS_APP_LABELS / SYSTEM_APP_LABELS: {unclassified}"
    )
    assert not do_nothing, (
        f"DO_NOTHING reverse FK(s) to User outside LANDPKS_APP_LABELS: {do_nothing}"
    )


# ---------------------------------------------------------------------------
# Closure test: the user-deletion cascade is hard-delete-safe
# ---------------------------------------------------------------------------


# Cron risks purging any closure model when there's an incoming FK with
# one of these on_deletes: PROTECT/RESTRICT raise at the ORM layer, and
# DO_NOTHING can raise IntegrityError at the DB layer (constraint fires
# when the FK isn't nullable and the referring row is still present).
CRON_CANNOT_PURGE = BLOCKING_ON_DELETE | {"DO_NOTHING"}

# Only these on_delete modes cascade through to the referring model —
# used by _build_user_deletion_closure when walking outward from User.
CASCADING_ON_DELETE = {"CASCADE", "SET_NULL", "SET_DEFAULT", "SET"}


def _build_user_deletion_closure():
    """Build the set of models that get soft-deleted when a User
    soft-deletes. Used by the closure structural test.

    Construction:
      - Start at User.
      - Follow CASCADE / SET_NULL / SET_DEFAULT / SET reverse FKs to
        find what Django's collector would cascade through (e.g. Site
        via Site.owner=CASCADE, collaboration.Membership via
        Membership.user=CASCADE). Skip SYSTEM_APP_LABELS apps — Django
        manages those itself and we don't want to walk into them.
      - Augment with all LANDPKS_APP_LABELS models. The cascade reaches
        them explicitly via User._soft_delete_with_cascade /
        Project.soft_delete_policy_action (e.g. solo-manager Projects,
        project-affiliated Sites), even when they aren't Django-
        reachable from User via reverse FKs."""
    from django.apps import apps as django_apps

    closure = {User}
    queue = [User]
    while queue:
        model = queue.pop()
        for rel in model._meta.related_objects:
            if rel.many_to_many:
                continue
            on_delete_name = rel.on_delete.__name__.upper()
            if on_delete_name not in CASCADING_ON_DELETE:
                continue  # PROTECT/RESTRICT/DO_NOTHING don't cascade.
            related_model = rel.related_model
            if related_model._meta.app_label in SYSTEM_APP_LABELS:
                continue
            if related_model not in closure:
                closure.add(related_model)
                queue.append(related_model)

    for app_label in LANDPKS_APP_LABELS:
        for model in django_apps.get_app_config(app_label).get_models():
            closure.add(model)
    return closure


def test_structural_user_deletion_closure_is_hard_delete_safe():
    """Hard-delete safety for the user-deletion cascade.

    For every model in the user-deletion closure (excluding User
    itself), assert that no FK pointing AT it is PROTECT / RESTRICT /
    DO_NOTHING — regardless of whether the FK originates inside or
    outside the closure. Such an FK could raise ProtectedError (ORM
    layer, PROTECT/RESTRICT) or IntegrityError (DB layer, DO_NOTHING)
    when the harddelete cron later tries to purge the closure model.

    User itself is excluded from this check because incoming FKs to
    User are the deletion gate's job — safedelete's collector raises
    `ProtectedError` for PROTECT/RESTRICT FKs at soft-delete time, and
    Test A above enforces classification of every reverse FK to User.

    Two failure modes this catches:

    1. **Within-closure blocking FK**: e.g. ProjectSettings.project =
       ForeignKey(Project, PROTECT). When the cron hard-deletes Project
       (a closure member), PROTECT raises. The cron has no topological
       ordering across models, so we can't rely on the dependent row
       being purged first.

    2. **External-to-closure blocking FK**: e.g. a future app adds
       SpecialData.site = ForeignKey(Site, PROTECT). The soft-delete
       gate would catch this (safedelete's collector walks the whole
       cascade tree), but the harddelete cron runs against already-
       soft-deleted users — a new external PROTECT/RESTRICT/DO_NOTHING
       FK added during someone's grace window would crash the cron.
       This test surfaces the risk in CI so schema changes don't
       silently break it.

    If this test fires, the options are: change the FK to CASCADE /
    SET_NULL, add the originating model's app to LANDPKS_APP_LABELS so
    it joins the explicit cascade, or wire the originating model in to
    a higher-level soft_delete_policy_action."""
    closure = _build_user_deletion_closure()

    bad = []
    for model in closure:
        if model is User:
            continue
        for rel in model._meta.related_objects:
            if rel.many_to_many:
                continue
            on_delete_name = rel.on_delete.__name__.upper()
            if on_delete_name in CRON_CANNOT_PURGE:
                bad.append(
                    f"{rel.related_model._meta.label}.{rel.field.name} → "
                    f"{model._meta.label} (on_delete={on_delete_name})"
                )

    assert not bad, (
        "User-deletion closure has closure model(s) referenced via "
        "blocking FK(s) — the harddelete cron would crash when these "
        f"models are purged: {bad}"
    )


# ---------------------------------------------------------------------------
# User.delete() gate
# ---------------------------------------------------------------------------


def test_delete_raises_user_deletion_blocked_error(user):
    """The model raises `UserDeletionBlockedError` (subclass of
    ValidationError). The message points to the diagnostic command;
    exception carries no structured blocker payload."""
    from apps.core.models.users import UserDeletionBlockedError

    mixer.blend(DataEntry, created_by=user)
    with pytest.raises(UserDeletionBlockedError) as exc_info:
        user.delete()
    # Subclass relationship preserved for backwards-compatibility callers.
    assert isinstance(exc_info.value, ValidationError)
    assert "show_deletion_blockers" in str(exc_info.value)
    user.refresh_from_db()
    assert user.deleted_at is None


def test_delete_raises_when_blockers_present(user):
    mixer.blend(DataEntry, created_by=user)
    with pytest.raises(ValidationError, match="undeletable data"):
        user.delete()
    user.refresh_from_db()
    assert user.deleted_at is None


def test_delete_succeeds_for_landpks_only_user(landpks_user):
    landpks_user.delete()
    landpks_user.refresh_from_db()
    assert landpks_user.deleted_at is not None


def test_force_hard_delete_is_not_gated(user):
    """The cron path (`force_policy=HARD_DELETE`) intentionally bypasses
    the gate. Verified with a non-project APPROVED Membership — which
    blocks at the gate (the policy override) but is CASCADE at the DB
    level, so the hard-delete itself succeeds."""
    landscape = mixer.blend(Landscape)
    CollaborationMembership.objects.create(
        membership_list=landscape.membership_list,
        user=user,
        user_role="MEMBER",
        membership_status=CollaborationMembership.APPROVED,
    )
    # Sanity: gate would refuse a soft-delete.
    with pytest.raises(ValidationError, match="undeletable data"):
        user.delete()

    # Hard-delete bypasses the gate cleanly.
    user.delete(force_policy=HARD_DELETE)
    assert not User.objects.all_with_deleted().filter(pk=user.pk).exists()


# ---------------------------------------------------------------------------
# Cascade behavior (when delete proceeds)
# ---------------------------------------------------------------------------


def test_unaffiliated_site_cascades_with_owner(user):
    site = Site.objects.create(
        name="unaffiliated", latitude=0, longitude=0, elevation=0, owner=user
    )
    note = SiteNote.objects.create(site=site, content="note", author=user)
    user.delete()
    site.refresh_from_db()
    note.refresh_from_db()
    assert site.deleted_at is not None
    assert note.deleted_at is not None


def test_sole_manager_project_cascades(user):
    """User is the only manager → project + membership_list + sites all
    soft-delete with the user."""
    project = mixer.blend(Project)
    project.add_manager(user)
    site = Site.objects.create(name="ps", latitude=0, longitude=0, elevation=0, project=project)
    membership_list_id = project.membership_list_id

    user.delete()

    project.refresh_from_db()
    site.refresh_from_db()
    assert project.deleted_at is not None
    assert site.deleted_at is not None
    # MembershipList soft-deleted via Project.soft_delete_policy_action.
    ml = MembershipList.objects.all_with_deleted().get(pk=membership_list_id)
    assert ml.deleted_at is not None


def test_co_managed_project_survives(user):
    """Project with a second manager survives; only the user's
    membership cascades (via Membership.user = CASCADE + SafeDelete)."""
    other = mixer.blend(User)
    project = mixer.blend(Project)
    project.add_manager(user)
    project.add_manager(other)
    site = Site.objects.create(name="cs", latitude=0, longitude=0, elevation=0, project=project)

    user.delete()

    project.refresh_from_db()
    site.refresh_from_db()
    assert project.deleted_at is None
    assert site.deleted_at is None
    # User's own Membership is gone.
    assert not CollaborationMembership.objects.filter(
        membership_list=project.membership_list, user=user
    ).exists()


def test_full_nested_cascade(user):
    """The big behavioral test: build the full nested footprint, soft-
    delete the user, assert every layer dies with them — and that a
    co-managed project on the side survives untouched."""
    # Sole-managed project with sites + soil data + a note.
    sole_project = mixer.blend(Project)
    sole_project.add_manager(user)
    sole_site = Site.objects.create(
        name="sole-s", latitude=0, longitude=0, elevation=0, project=sole_project
    )
    add_soil_data_to_site(sole_site)
    sole_note = SiteNote.objects.create(site=sole_site, content="sn", author=user)
    sole_ml_id = sole_project.membership_list_id

    # Co-managed project that must survive.
    other = mixer.blend(User)
    co_project = mixer.blend(Project)
    co_project.add_manager(user)
    co_project.add_manager(other)
    co_site = Site.objects.create(
        name="co-s", latitude=0, longitude=0, elevation=0, project=co_project
    )
    co_note = SiteNote.objects.create(site=co_site, content="cn", author=user)

    # Unaffiliated owned site with soil data + a note.
    own_site = Site.objects.create(name="own-s", latitude=0, longitude=0, elevation=0, owner=user)
    own_note = SiteNote.objects.create(site=own_site, content="on", author=user)

    user.delete()

    # Sole-managed subtree: all soft-deleted.
    sole_project.refresh_from_db()
    sole_site.refresh_from_db()
    sole_note.refresh_from_db()
    assert sole_project.deleted_at is not None
    assert sole_site.deleted_at is not None
    assert sole_note.deleted_at is not None
    ml = MembershipList.objects.all_with_deleted().get(pk=sole_ml_id)
    assert ml.deleted_at is not None

    # Unaffiliated subtree: gone.
    own_site.refresh_from_db()
    own_note.refresh_from_db()
    assert own_site.deleted_at is not None
    assert own_note.deleted_at is not None

    # Co-managed survives.
    co_project.refresh_from_db()
    co_site.refresh_from_db()
    co_note.refresh_from_db()
    assert co_project.deleted_at is None
    assert co_site.deleted_at is None
    # SiteNote.author on surviving rows is nulled by SET_NULL.
    assert co_note.deleted_at is None
    assert co_note.author is None


# ---------------------------------------------------------------------------
# Solo-manager detection
# ---------------------------------------------------------------------------


def test_solo_manager_query_sole(user):
    project = mixer.blend(Project)
    project.add_manager(user)
    assert list(user._solo_manager_projects()) == [project]


def test_solo_manager_query_with_co_manager(user):
    other = mixer.blend(User)
    project = mixer.blend(Project)
    project.add_manager(user)
    project.add_manager(other)
    assert list(user._solo_manager_projects()) == []


def test_solo_manager_query_non_manager(user):
    project = mixer.blend(Project)
    project.add_contributor(user)
    assert list(user._solo_manager_projects()) == []


# ---------------------------------------------------------------------------
# Project.soft_delete_policy_action — outside the user cascade
# ---------------------------------------------------------------------------


def test_project_soft_delete_cleans_up_membership_list():
    """Directly soft-delete a Project (no user involved): MembershipList
    and its Memberships go with it. Holds for every project-deletion
    path, not just the user cascade."""
    project = mixer.blend(Project)
    user = mixer.blend(User)
    project.add_manager(user)
    ml_id = project.membership_list_id
    membership = CollaborationMembership.objects.get(membership_list_id=ml_id, user=user)

    project.delete()

    ml = MembershipList.objects.all_with_deleted().get(pk=ml_id)
    assert ml.deleted_at is not None
    membership.refresh_from_db()
    assert membership.deleted_at is not None


# ---------------------------------------------------------------------------
# Undelete — restoring solo-manager Projects and their subtrees
# ---------------------------------------------------------------------------


def test_undelete_restores_sole_manager_project(user):
    """User.undelete must restore Projects this user was the sole manager
    of at deletion time. They're not reachable from User via a reverse FK,
    so safedelete's standard undelete-walker doesn't find them — the
    explicit walk in _undelete_solo_manager_projects does."""
    project = mixer.blend(Project)
    project.add_manager(user)

    user.delete()
    project.refresh_from_db()
    assert project.deleted_at is not None  # sanity

    user.undelete()
    project.refresh_from_db()
    assert project.deleted_at is None


def test_undelete_restores_membership_list_of_sole_manager_project(user):
    """Project.undelete must restore the MembershipList — ML is upstream
    of Project in DB terms (the FK column lives on Project), so neither
    safedelete's cascade-walker nor the FK-accessor reach it without an
    explicit lookup via all_objects."""
    project = mixer.blend(Project)
    project.add_manager(user)
    ml_id = project.membership_list_id

    user.delete()
    ml = MembershipList.all_objects.get(pk=ml_id)
    assert ml.deleted_at is not None  # sanity

    user.undelete()
    ml.refresh_from_db()
    assert ml.deleted_at is None


def test_undelete_restores_full_sole_manager_subtree(user):
    """The behavioral round-trip: a sole-managed Project's Sites, soil
    data, MembershipList, and other Memberships all come back when the
    user is undeleted. Mirrors the cascade test on the delete side."""
    other = mixer.blend(User)
    project = mixer.blend(Project)
    project.add_manager(user)
    project.add_contributor(other)
    site = Site.objects.create(name="ps", latitude=0, longitude=0, elevation=0, project=project)
    add_soil_data_to_site(site)
    note = SiteNote.objects.create(site=site, content="n", author=user)
    ml_id = project.membership_list_id
    other_membership = CollaborationMembership.objects.get(membership_list_id=ml_id, user=other)

    user.delete()
    user.undelete()

    project.refresh_from_db()
    site.refresh_from_db()
    note.refresh_from_db()
    other_membership.refresh_from_db()
    ml = MembershipList.all_objects.get(pk=ml_id)

    assert project.deleted_at is None
    assert site.deleted_at is None
    assert note.deleted_at is None
    assert ml.deleted_at is None
    assert other_membership.deleted_at is None


def test_undelete_does_not_touch_co_managed_projects(user):
    """Co-managed Projects were never deleted in the first place. They
    must still be active after the user soft-deletes and then undeletes.
    Verifies the helper doesn't over-restore."""
    other = mixer.blend(User)
    project = mixer.blend(Project)
    project.add_manager(user)
    project.add_manager(other)

    user.delete()
    project.refresh_from_db()
    assert project.deleted_at is None  # sanity: co-managed survives delete

    user.undelete()
    project.refresh_from_db()
    assert project.deleted_at is None  # still active


def test_undelete_skips_already_active_managed_projects(user):
    """If the user's manager Membership points at an already-active
    Project (e.g. some external admin undeleted it independently between
    user.delete() and user.undelete()), don't double-undelete it."""
    project = mixer.blend(Project)
    project.add_manager(user)

    user.delete()
    # Simulate an external undelete of the project before user comes back.
    project.refresh_from_db()
    project.undelete()
    project.refresh_from_db()
    project_deleted_at_before_undelete = project.deleted_at
    assert project_deleted_at_before_undelete is None

    # User undelete should not crash and the project stays active.
    user.undelete()
    project.refresh_from_db()
    assert project.deleted_at is None
