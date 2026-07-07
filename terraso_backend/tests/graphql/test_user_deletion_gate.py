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

Model-layer behavior — `deletion_blockers()`, the `User.delete()` gate,
the cascade, the structural drift detectors — is covered by
`tests/core/models/test_user_deletion_gate.py`. This file covers the
two callers that wrap the gate with caller-specific UX:

  * `UserDeleteMutation` — returns structured `blockers` payload when
    blocked, runs the cascade when clean.
  * `UserAdmin.delete_model` / `delete_queryset` — single-delete shows
    a red banner; bulk-delete partitions blocked vs. clean and surfaces
    a single warning banner."""

from unittest.mock import patch

import pytest
from django.contrib import messages
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.base import BaseStorage
from django.test import RequestFactory
from mixer.backend.django import mixer

from apps.core.admin import UserAdmin
from apps.core.models import Group, User
from apps.shared_data.models import DataEntry

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# GraphQL UserDeleteMutation
# ---------------------------------------------------------------------------

DELETE_USER_MUTATION = """
mutation deleteUser($input: UserDeleteMutationInput!) {
  deleteUser(input: $input) {
    user { email }
    blockers { model field count }
    errors
  }
}
"""


def test_mutation_clean_user_returns_user_and_empty_blockers(client_query, users):
    """Clean self-delete: payload returns the user, blockers=[]."""
    user = users[0]
    response = client_query(DELETE_USER_MUTATION, variables={"input": {"id": str(user.id)}}).json()
    payload = response["data"]["deleteUser"]
    assert payload["user"]["email"] == user.email
    assert payload["blockers"] == []
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
    assert msgs[0].level == messages.ERROR
    assert "undeletable data" in msgs[0].message


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


def test_admin_get_deleted_objects_uses_our_blocker_list():
    """The admin's delete-confirmation page lists "protected related objects"
    from a list we control: source-of-truth is `deletion_blockers()`, not
    Django's collector. This means:
      * soft-deleted PROTECT rows DON'T appear (Django would list them)
      * active blocker rows DO appear
    Locks in agreement between the admin and the GraphQL mutation."""
    target = mixer.blend(User)
    # Active DataEntry (PROTECT); should appear in `protected` via our gate.
    entry = mixer.blend(DataEntry, created_by=target)
    # Soft-deleted Group (PROTECT); should NOT appear (it's not an active blocker).
    group = mixer.blend(Group, created_by=target)
    group.delete()

    staff = mixer.blend(User, is_staff=True, is_superuser=True)
    admin = UserAdmin(User, AdminSite())
    request = _make_admin_request(staff)

    _, _, _, protected = admin.get_deleted_objects([target], request)

    joined = " ".join(str(p) for p in protected)
    # Active blocker shows.
    assert "shared_data.DataEntry" in joined
    # Soft-deleted PROTECT row does NOT show.
    assert "core.Group" not in joined
    # IDs render as admin-change-page links.
    assert f'href="/admin/shared_data/dataentry/{entry.pk}/change/"' in joined
