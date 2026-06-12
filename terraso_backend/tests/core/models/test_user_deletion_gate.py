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

"""Tests for the User soft-delete gate (backend/docs/user_soft_delete_plan.md).

Three layers under test:

  * `User.deletion_blockers()` — the rule that defines undeletable data.
  * `User.delete()` — the enforcement floor: raises on the soft-delete path
    when blockers exist; does not fire on `force_policy=HARD_DELETE`.
  * `User.soft_delete_policy_action` / `Project.soft_delete_policy_action`
    — the cascade that tears down the user's landpks footprint and
    sole-manager projects.

Plus structural tests that catch schema drift in CI:

  * **Test A**: every reverse FK to User is classified into exactly one
    of the five legal buckets.
  * **Closure test**: the transitive closure of models soft-deleted by
    `user.delete()` has no model referenced via a blocking FK —
    PROTECT / RESTRICT / DO_NOTHING — from inside or outside the
    closure. Together with the gate, this proves the harddelete cron
    can purge the closure without crashing on a constraint."""

import pytest
from django.core.exceptions import ValidationError
from mixer.backend.django import mixer
from safedelete.models import HARD_DELETE

from apps.collaboration.models import Membership as CollaborationMembership
from apps.collaboration.models import MembershipList
from apps.core.models import Group, Landscape, TaxonomyTerm, User
from apps.core.models.users import (
    BLOCKING_ON_DELETE,
    LANDPKS_APP_LABELS,
    SYSTEM_APP_LABELS,
)
from apps.project_management.models import Project, Site
from apps.project_management.models.site_notes import SiteNote
from apps.shared_data.models import DataEntry, VisualizationConfig
from apps.story_map.models import StoryMap
from tests.utils import add_soil_data_to_site

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def landpks_user():
    """A user whose only footprint is landpks data: an unaffiliated site
    with soil data + depth intervals + a note, plus a sole-manager
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
    legal bucket. A future PR that adds an unhandled FK fails here."""
    unclassified = []
    for rel in User._meta.related_objects:
        # M2M reverse relations are skipped (through-rows auto-clean).
        if rel.many_to_many:
            continue
        related_model = rel.related_model
        app = related_model._meta.app_label

        bucket = None
        if app in LANDPKS_APP_LABELS:
            bucket = "landpks"
        elif app in SYSTEM_APP_LABELS:
            bucket = "system"
        elif related_model._meta.label == "collaboration.Membership":
            bucket = "membership-policy-override"
        else:
            on_delete_name = rel.on_delete.__name__.upper()
            if on_delete_name in BLOCKING_ON_DELETE:
                bucket = f"auto-block ({on_delete_name})"
            elif on_delete_name in {"CASCADE", "SET_NULL", "SET_DEFAULT", "SET"}:
                bucket = f"auto-allow ({on_delete_name})"

        if bucket is None:
            unclassified.append(
                f"{related_model._meta.label}.{rel.field.name} (on_delete={rel.on_delete.__name__})"
            )

    assert not unclassified, (
        "Unclassified reverse FK(s) to User — extend deletion_blockers() "
        f"or one of the app-label allowlists: {unclassified}"
    )


# ---------------------------------------------------------------------------
# Closure test: the user-deletion cascade is hard-delete-safe
# ---------------------------------------------------------------------------


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
        Project.soft_delete_policy_action (e.g. sole-manager Projects,
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
            if on_delete_name in BLOCKING_ON_DELETE:
                continue  # Won't cascade through this rel.
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
    outside the closure. Such an FK could raise ProtectedError when the
    harddelete cron later tries to purge the closure model.

    User itself is excluded from this check because incoming FKs to
    User are the deletion gate's job — see User.deletion_blockers() and
    Test A.

    Two failure modes this catches:

    1. **Within-closure blocking FK**: e.g. ProjectSettings.project =
       ForeignKey(Project, PROTECT). When the cron hard-deletes Project
       (a closure member), PROTECT raises. The cron has no topological
       ordering across models, so we can't rely on the dependent row
       being purged first.

    2. **External-to-closure blocking FK**: e.g. a future app adding
       SpecialData.site = ForeignKey(Site, PROTECT). The gate doesn't
       see SpecialData — deletion_blockers() only walks reverse FKs one
       level from User — so without this test the failure would
       surface as a runtime cron crash rather than a CI failure.

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
            if on_delete_name in BLOCKING_ON_DELETE:
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
# deletion_blockers() — coverage for each kind of undeletable data
# ---------------------------------------------------------------------------


def _blocker_models(blockers):
    return {b["model"] for b in blockers}


def test_deletion_blockers_empty_for_landpks_only_user(landpks_user):
    assert landpks_user.deletion_blockers() == []


def test_deletion_blockers_empty_for_brand_new_user():
    user = mixer.blend(User)
    assert user.deletion_blockers() == []


def test_dataentry_created_by_blocks(user):
    """DataEntry.created_by is DO_NOTHING — must auto-block."""
    mixer.blend(DataEntry, created_by=user)
    blockers = user.deletion_blockers()
    assert "shared_data.DataEntry" in _blocker_models(blockers)


def test_visualization_config_blocks(user):
    """VisualizationConfig.created_by is PROTECT — auto-block."""
    mixer.blend(VisualizationConfig, created_by=user)
    blockers = user.deletion_blockers()
    assert "shared_data.VisualizationConfig" in _blocker_models(blockers)


def test_story_map_blocks(user):
    """StoryMap.created_by is DO_NOTHING — auto-block."""
    mixer.blend(StoryMap, created_by=user)
    blockers = user.deletion_blockers()
    assert "story_map.StoryMap" in _blocker_models(blockers)


def test_group_created_by_blocks(user):
    mixer.blend(Group, created_by=user)
    blockers = user.deletion_blockers()
    assert "core.Group" in _blocker_models(blockers)


def test_landscape_created_by_blocks(user):
    mixer.blend(Landscape, created_by=user)
    blockers = user.deletion_blockers()
    assert "core.Landscape" in _blocker_models(blockers)


def test_taxonomy_term_created_by_blocks(user):
    mixer.blend(TaxonomyTerm, created_by=user)
    blockers = user.deletion_blockers()
    assert "core.TaxonomyTerm" in _blocker_models(blockers)


def test_non_project_approved_membership_blocks(user):
    """Policy override: a non-project APPROVED Membership blocks even
    though Membership.user is CASCADE."""
    landscape = mixer.blend(Landscape)
    CollaborationMembership.objects.create(
        membership_list=landscape.membership_list,
        user=user,
        user_role="MEMBER",
        membership_status=CollaborationMembership.APPROVED,
    )
    blockers = user.deletion_blockers()
    assert any("Membership" in b["model"] for b in blockers)


def test_pending_membership_does_not_block(user):
    """Pending invites are CASCADE-safe; only APPROVED counts."""
    landscape = mixer.blend(Landscape)
    CollaborationMembership.objects.create(
        membership_list=landscape.membership_list,
        user=user,
        user_role="MEMBER",
        membership_status=CollaborationMembership.PENDING,
    )
    blockers = user.deletion_blockers()
    assert not any("Membership" in b["model"] for b in blockers)


def test_project_membership_does_not_block(user):
    """Project memberships are torn down by the cascade — not blockers."""
    project = mixer.blend(Project)
    project.add_manager(user)
    blockers = user.deletion_blockers()
    assert not any("Membership" in b["model"] for b in blockers)


def test_membership_classification_mixed(user):
    """One project membership and one Group/Landscape membership for the
    same user: only the non-project one shows up as a blocker. Locks the
    project__isnull traversal through the MembershipList → Project hop."""
    project = mixer.blend(Project)
    project.add_manager(user)
    landscape = mixer.blend(Landscape)
    CollaborationMembership.objects.create(
        membership_list=landscape.membership_list,
        user=user,
        user_role="MEMBER",
        membership_status=CollaborationMembership.APPROVED,
    )
    blockers = user.deletion_blockers()
    membership_blockers = [b for b in blockers if "Membership" in b["model"]]
    assert len(membership_blockers) == 1
    assert membership_blockers[0]["count"] == 1


def test_soft_deleted_blocker_still_blocks(user):
    """A soft-deleted StoryMap still counts: it's a not-yet-purged
    DO_NOTHING row that would crash the harddelete cron. force_visibility
    must include it until the cron sweeps it away."""
    story_map = mixer.blend(StoryMap, created_by=user)
    story_map.delete()  # safedelete soft-delete
    blockers = user.deletion_blockers()
    assert "story_map.StoryMap" in _blocker_models(blockers)


def test_landpks_app_relations_never_block(user):
    """Sanity: the explicit-cascade allowlist holds even for a heavy
    landpks footprint."""
    Site.objects.create(name="s", latitude=0, longitude=0, elevation=0, owner=user)
    project = mixer.blend(Project)
    project.add_manager(user)
    Site.objects.create(name="s2", latitude=0, longitude=0, elevation=0, project=project)
    assert user.deletion_blockers() == []


# ---------------------------------------------------------------------------
# User.delete() gate
# ---------------------------------------------------------------------------


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
    blocks at the gate (policy override clause 5) but is CASCADE at the
    DB level, so hard-delete actually succeeds. (DO_NOTHING blockers
    would also bypass the gate but then crash on FK constraints at the
    DB — a pre-existing risk acknowledged in the plan, Concerns #6.)"""
    landscape = mixer.blend(Landscape)
    CollaborationMembership.objects.create(
        membership_list=landscape.membership_list,
        user=user,
        user_role="MEMBER",
        membership_status=CollaborationMembership.APPROVED,
    )
    # Sanity: gate would refuse a soft-delete.
    assert user.deletion_blockers()

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
# Sole-manager detection
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
# Undelete — restoring sole-manager Projects and their subtrees
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
