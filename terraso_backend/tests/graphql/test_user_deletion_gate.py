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

"""Presentation-layer tests for the User soft-delete gate
(backend/docs/user_soft_delete_plan.md).

Model-layer behavior — deletion_blockers(), the User.delete() gate, the
cascade, the structural drift detectors — is covered by
tests/core/models/test_user_deletion_gate.py. This file covers the
two callers that wrap the gate with caller-specific UX:

  * UserDeleteMutation — returns structured `blockers` payload when
    blocked, runs the cascade when clean.
  * UserAdmin.delete_model / delete_queryset — single-delete shows a red
    banner; bulk-delete partitions blocked vs. clean and surfaces a
    single warning banner."""

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


def test_mutation_user_with_blockers_returns_blockers_and_null_user(client_query, users):
    """Blocked self-delete: payload returns user=null with structured
    blockers; the User row is NOT soft-deleted."""
    user = users[0]
    mixer.blend(DataEntry, created_by=user)

    response = client_query(DELETE_USER_MUTATION, variables={"input": {"id": str(user.id)}}).json()
    payload = response["data"]["deleteUser"]

    assert payload["user"] is None
    assert payload["blockers"]
    assert any("DataEntry" in b["model"] for b in payload["blockers"])
    # User is still active.
    user.refresh_from_db()
    assert user.deleted_at is None


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
