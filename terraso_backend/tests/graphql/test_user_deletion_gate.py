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

"""Presentation-layer tests for the User soft-delete gate.

Model-layer behavior — the `User.delete()` gate, the cascade, and the
structural drift detectors — is covered by
`tests/core/models/test_user_deletion_gate.py`. Blocker-inventory
coverage lives in `tests/core/commands/test_show_deletion_blockers.py`.
This file covers the two callers that wrap the gate with caller-
specific UX:

  * `UserDeleteMutation` — returns `user=null` when blocked and files
    a HubSpot ticket + sets the pending pref; runs the cascade when
    clean.
  * `UserAdmin.delete_model` / `delete_queryset` — single-delete shows
    a red banner; bulk-delete partitions blocked vs. clean and surfaces
    a single warning banner. Both confirmation pages get a diagnostic
    banner pointing at the show_deletion_blockers command."""

from unittest.mock import patch

import pytest
from django.contrib import messages
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.base import BaseStorage
from django.test import RequestFactory
from mixer.backend.django import mixer

from apps.core.admin import UserAdmin
from apps.core.models import User
from apps.shared_data.models import DataEntry

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# GraphQL UserDeleteMutation
# ---------------------------------------------------------------------------

DELETE_USER_MUTATION = """
mutation deleteUser($input: UserDeleteMutationInput!) {
  deleteUser(input: $input) {
    user { email }
    errors
  }
}
"""


def test_mutation_clean_user_returns_user(client_query, users):
    """Clean self-delete: payload returns the user; row is gone."""
    user = users[0]
    response = client_query(DELETE_USER_MUTATION, variables={"input": {"id": str(user.id)}}).json()
    payload = response["data"]["deleteUser"]
    assert payload["user"]["email"] == user.email
    assert not User.objects.filter(pk=user.pk).exists()


@patch("apps.core.hubspot.create_account_deletion_ticket")
def test_mutation_blocked_user_returns_null_user(mock_ticket, client_query, users):
    """Blocked self-delete: payload returns user=null; the User row is
    NOT soft-deleted (HubSpot integration covered separately below)."""
    mock_ticket.return_value = True
    user = users[0]
    mixer.blend(DataEntry, created_by=user)

    response = client_query(DELETE_USER_MUTATION, variables={"input": {"id": str(user.id)}}).json()
    payload = response["data"]["deleteUser"]

    assert payload["user"] is None
    # User is still active.
    user.refresh_from_db()
    assert user.deleted_at is None


@patch("apps.core.hubspot.create_account_deletion_ticket")
def test_mutation_blocked_branch_files_hubspot_ticket_and_sets_pref(
    mock_ticket, client_query, users
):
    """Blocked self-delete falls back to the manual-cleanup flow: it sets
    the pending-deletion pref and files a HubSpot ticket. Support runs
    the show_deletion_blockers command out-of-band for specifics."""
    from apps.core.models import UserPreference
    from apps.core.models.users import USER_PREFS_KEY_ACCOUNT_DELETION

    mock_ticket.return_value = True
    user = users[0]
    mixer.blend(DataEntry, created_by=user)

    client_query(DELETE_USER_MUTATION, variables={"input": {"id": str(user.id)}}).json()

    mock_ticket.assert_called_once_with(user)

    # Pending-deletion pref is now "true" so re-login routes to the pending screen.
    pref = UserPreference.objects.get(user_id=user.id, key=USER_PREFS_KEY_ACCOUNT_DELETION)
    assert pref.value.lower() == "true"


@patch("apps.core.hubspot.create_account_deletion_ticket")
def test_mutation_blocked_branch_is_idempotent_on_retry(mock_ticket, client_query, users):
    """If the user re-fires the mutation while still blocked, the helper
    short-circuits on the existing 'true' pref — no second ticket."""
    mock_ticket.return_value = True
    user = users[0]
    mixer.blend(DataEntry, created_by=user)

    client_query(DELETE_USER_MUTATION, variables={"input": {"id": str(user.id)}}).json()
    client_query(DELETE_USER_MUTATION, variables={"input": {"id": str(user.id)}}).json()

    assert mock_ticket.call_count == 1


@patch("apps.core.hubspot.create_account_deletion_ticket")
def test_mutation_blocked_branch_returns_error_when_hubspot_fails(mock_ticket, client_query, users):
    """Blocked + HubSpot down: the payload carries a layered error (so
    the client knows the support handoff didn't succeed and the pref
    wasn't set). User stays active, pref stays "false" so retry works."""
    from apps.core.models import UserPreference
    from apps.core.models.users import USER_PREFS_KEY_ACCOUNT_DELETION

    mock_ticket.return_value = False  # HubSpot reports failure
    user = users[0]
    mixer.blend(DataEntry, created_by=user)

    response = client_query(DELETE_USER_MUTATION, variables={"input": {"id": str(user.id)}}).json()
    payload = response["data"]["deleteUser"]

    assert payload["user"] is None
    # Layered error — client knows the ticket failed and can retry.
    assert payload["errors"]
    assert "ticket" in payload["errors"][0]["message"].lower()
    # Pref stays "false" so the retry isn't short-circuited.
    pending = UserPreference.objects.filter(
        user_id=user.id, key=USER_PREFS_KEY_ACCOUNT_DELETION, value__iexact="true"
    )
    assert not pending.exists()
    # User remains active.
    user.refresh_from_db()
    assert user.deleted_at is None


def test_retry_after_clean_delete_is_rejected_at_auth_layer(client_query, users):
    """After a successful clean delete, retrying the mutation with the
    same JWT is rejected by the auth middleware (User.objects.get(pk=...)
    excludes soft-deleted users → "User not found for JWT token" → 401).
    The mutation never runs. This is the "other-device bouncing" property
    that lets us drop the explicit re-auth-after-delete code path.

    Not really "idempotence" on the mutation — the clean-delete path is
    destructive — but locks in graceful handling at the layer that
    actually owns it."""
    user = users[0]
    user.delete()  # soft-delete via the normal path

    response = client_query(DELETE_USER_MUTATION, variables={"input": {"id": str(user.id)}})

    # 401 from auth middleware; mutation never reached.
    assert response.status_code == 401
    # User stays soft-deleted; we don't accidentally undelete them.
    user.refresh_from_db()
    assert user.deleted_at is not None


# ---------------------------------------------------------------------------
# UserAdmin
# ---------------------------------------------------------------------------


class _InMemoryMessageStorage(BaseStorage):
    """Minimal messages storage so RequestFactory-built admin requests
    can call self.message_user() without dragging in session middleware."""

    def __init__(self, request):
        super().__init__(request)
        self._recorded = []

    def _get(self, *args, **kwargs):
        return [], True

    def _store(self, messages_list, response, *args, **kwargs):
        return []

    def add(self, level, message, extra_tags=""):
        self._recorded.append(messages.Message(level, message, extra_tags))


def _make_admin_request(staff_user):
    factory = RequestFactory()
    request = factory.post("/admin/")
    request.user = staff_user
    request._messages = _InMemoryMessageStorage(request)
    return request


def _captured_messages(request):
    return request._messages._recorded


def test_admin_delete_model_shows_banner_and_skips_delete_for_blocked_user():
    staff = mixer.blend(User, is_staff=True, is_superuser=True)
    blocked = mixer.blend(User)
    mixer.blend(DataEntry, created_by=blocked)

    admin = UserAdmin(User, AdminSite())
    request = _make_admin_request(staff)
    admin.delete_model(request, blocked)

    blocked.refresh_from_db()
    assert blocked.deleted_at is None  # NOT deleted
    msgs = _captured_messages(request)
    assert len(msgs) == 1
    assert msgs[0].level == messages.WARNING
    assert "Skipped 1 user" in msgs[0].message
    assert blocked.email in msgs[0].message
    assert "show_deletion_blockers" in msgs[0].message


def test_admin_delete_model_deletes_clean_user():
    staff = mixer.blend(User, is_staff=True, is_superuser=True)
    clean = mixer.blend(User)

    admin = UserAdmin(User, AdminSite())
    request = _make_admin_request(staff)
    admin.delete_model(request, clean)

    assert not User.objects.filter(pk=clean.pk).exists()
    assert _captured_messages(request) == []


def test_admin_delete_queryset_partitions_blocked_and_clean():
    """Bulk delete: clean users delete, blocked ones surface in a single
    warning banner — no exception interrupts the batch."""
    staff = mixer.blend(User, is_staff=True, is_superuser=True)
    clean = mixer.blend(User)
    blocked = mixer.blend(User)
    mixer.blend(DataEntry, created_by=blocked)

    admin = UserAdmin(User, AdminSite())
    request = _make_admin_request(staff)
    qs = User.objects.filter(pk__in=[clean.pk, blocked.pk])
    admin.delete_queryset(request, qs)

    # Clean is gone; blocked remains.
    assert not User.objects.filter(pk=clean.pk).exists()
    blocked.refresh_from_db()
    assert blocked.deleted_at is None

    msgs = _captured_messages(request)
    assert len(msgs) == 1
    assert msgs[0].level == messages.WARNING
    assert blocked.email in msgs[0].message


def test_admin_suppresses_success_message_when_single_delete_blocked():
    """When `delete_model` catches UserDeletionBlockedError, Django's stock
    "was deleted successfully" (fired by `response_delete` right after)
    must be suppressed — otherwise staff see red-error + green-success
    banners side by side."""
    staff = mixer.blend(User, is_staff=True, is_superuser=True)
    target = mixer.blend(User)
    mixer.blend(DataEntry, created_by=target)  # blocker

    admin = UserAdmin(User, AdminSite())
    request = _make_admin_request(staff)
    admin.delete_model(request, target)
    # Simulate Django's forthcoming success message from response_delete.
    admin.message_user(request, "was deleted successfully", level=messages.SUCCESS)

    msgs = _captured_messages(request)
    assert not any(m.level == messages.SUCCESS for m in msgs)


def test_admin_suppresses_success_message_when_any_bulk_delete_blocked():
    """delete_selected fires 'Successfully deleted N users' from the queryset
    count, ignoring what was actually deleted. Suppress it when any user
    was skipped so the count isn't misleading."""
    staff = mixer.blend(User, is_staff=True, is_superuser=True)
    clean = mixer.blend(User)
    blocked = mixer.blend(User)
    mixer.blend(DataEntry, created_by=blocked)

    admin = UserAdmin(User, AdminSite())
    request = _make_admin_request(staff)
    qs = User.objects.filter(pk__in=[clean.pk, blocked.pk])
    admin.delete_queryset(request, qs)
    # Simulate Django's forthcoming success message from delete_selected.
    admin.message_user(request, "Successfully deleted 2 users.", level=messages.SUCCESS)

    msgs = _captured_messages(request)
    assert not any(m.level == messages.SUCCESS for m in msgs)


def test_admin_get_deleted_objects_never_refuses():
    """The confirmation button always renders — protected is always empty.
    `User.delete()` is the source of truth; blocked deletes surface as
    a "Skipped" warning after clicking confirm. Verified even with an
    active DataEntry (real blocker) — Django would normally refuse, we
    let the confirmation render."""
    staff = mixer.blend(User, is_staff=True, is_superuser=True)
    target = mixer.blend(User)
    mixer.blend(DataEntry, created_by=target)  # active PROTECT FK

    admin = UserAdmin(User, AdminSite())
    request = _make_admin_request(staff)
    _to_delete, _model_count, _perms_needed, protected = admin.get_deleted_objects(
        [target], request
    )
    assert protected == []


def test_admin_get_deleted_objects_fires_warning_when_blockers_exist():
    """On the confirmation-page render, an informative warning lists the
    actual blockers (via `deletion_blockers`, the same source
    `show_deletion_blockers` uses) and points staff at the CLI for
    row-level detail."""
    staff = mixer.blend(User, is_staff=True, is_superuser=True)
    target = mixer.blend(User)
    mixer.blend(DataEntry, created_by=target)

    admin = UserAdmin(User, AdminSite())
    request = _make_admin_request(staff)
    admin.get_deleted_objects([target], request)

    msgs = _captured_messages(request)
    warnings_ = [m for m in msgs if m.level == messages.WARNING]
    assert any("Deletion would be blocked by" in m.message for m in warnings_)
    assert any("shared_data.DataEntry" in m.message for m in warnings_)
    assert any("show_deletion_blockers" in m.message for m in warnings_)


def test_admin_get_deleted_objects_no_warning_when_clean():
    """No blockers → no warning banner. Confirmation page renders
    without any noise."""
    staff = mixer.blend(User, is_staff=True, is_superuser=True)
    target = mixer.blend(User)  # nothing blocking

    admin = UserAdmin(User, AdminSite())
    request = _make_admin_request(staff)
    admin.get_deleted_objects([target], request)

    warnings_ = [m for m in _captured_messages(request) if m.level == messages.WARNING]
    assert warnings_ == []


def test_admin_get_deleted_objects_ignores_soft_deleted_blockers():
    """Soft-deleted PROTECT rows shouldn't surface in the blockers list
    — `deletion_blockers` filters them, so they don't appear in the
    warning banner."""
    from apps.story_map.models import StoryMap

    staff = mixer.blend(User, is_staff=True, is_superuser=True)
    target = mixer.blend(User)
    story_map = mixer.blend(StoryMap, created_by=target)
    story_map.delete()  # soft-delete

    admin = UserAdmin(User, AdminSite())
    request = _make_admin_request(staff)
    admin.get_deleted_objects([target], request)

    warnings_ = [m for m in _captured_messages(request) if m.level == messages.WARNING]
    assert warnings_ == []  # nothing to report — soft-deleted rows filtered
