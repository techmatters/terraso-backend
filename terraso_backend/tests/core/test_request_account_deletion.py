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

"""Tests for `request_account_deletion(user)` — the shared helper that
sets the pending-deletion pref and files the HubSpot ticket.

Contract:
  * Ticket fires BEFORE pref save. If HubSpot fails, pref stays "false"
    and `TicketCreationError` is raised so the caller can retry.
  * Idempotent on the second call: if the pref is already "true", no
    second ticket is filed."""

from unittest.mock import patch

import pytest
from mixer.backend.django import mixer

from apps.core.models import User, UserPreference
from apps.core.models.users import (
    USER_PREFS_KEY_ACCOUNT_DELETION,
    TicketCreationError,
    request_account_deletion,
)

pytestmark = pytest.mark.django_db


@patch("apps.core.hubspot.create_account_deletion_ticket")
def test_fires_ticket_and_sets_pref_on_first_call(mock_ticket):
    mock_ticket.return_value = True
    user = mixer.blend(User)

    request_account_deletion(user)

    mock_ticket.assert_called_once_with(user)
    pref = UserPreference.objects.get(user_id=user.id, key=USER_PREFS_KEY_ACCOUNT_DELETION)
    assert pref.value.lower() == "true"


@patch("apps.core.hubspot.create_account_deletion_ticket")
def test_idempotent_when_pref_already_true(mock_ticket):
    """Second call short-circuits: no duplicate ticket."""
    mock_ticket.return_value = True
    user = mixer.blend(User)

    request_account_deletion(user)
    request_account_deletion(user)

    assert mock_ticket.call_count == 1


@patch("apps.core.hubspot.create_account_deletion_ticket")
def test_raises_and_leaves_pref_unchanged_when_ticket_fails(mock_ticket):
    """Ticket-before-pref ordering: if HubSpot reports failure, raise
    `TicketCreationError` and keep the pref at "false" so the caller's
    error path lets the user retry. This is the key contract that
    prevents the silent permanent-failure mode."""
    mock_ticket.return_value = False
    user = mixer.blend(User)

    with pytest.raises(TicketCreationError):
        request_account_deletion(user)

    pref = UserPreference.objects.get(user_id=user.id, key=USER_PREFS_KEY_ACCOUNT_DELETION)
    assert pref.value.lower() != "true"


@patch("apps.core.hubspot.create_account_deletion_ticket")
def test_retryable_after_ticket_failure(mock_ticket):
    """After a HubSpot failure, the next attempt succeeds and sets the pref
    — proves idempotence didn't lock the user out."""
    user = mixer.blend(User)

    mock_ticket.return_value = False
    with pytest.raises(TicketCreationError):
        request_account_deletion(user)

    mock_ticket.return_value = True
    request_account_deletion(user)

    pref = UserPreference.objects.get(user_id=user.id, key=USER_PREFS_KEY_ACCOUNT_DELETION)
    assert pref.value.lower() == "true"
    assert mock_ticket.call_count == 2
