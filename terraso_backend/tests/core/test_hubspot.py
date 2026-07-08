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

"""Tests for `create_account_deletion_ticket` — the HTTP call is
mocked; we assert on the body payload and on the dry-run / no-email
short-circuits. The ticket body is deliberately minimal (user identity
only); support runs `show_deletion_blockers` out-of-band for details."""

from unittest.mock import Mock, patch

import pytest
from django.test import override_settings
from mixer.backend.django import mixer

from apps.core.hubspot import create_account_deletion_ticket
from apps.core.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _force_real_http(settings):
    """Body-rendering tests need a real HTTP call to inspect the payload.
    Force HUBSPOT_DRY_RUN=False here so a local .env enabling dry-run
    doesn't make these tests pass-by-skipping the network. The one test
    that specifically exercises the dry-run path re-overrides."""
    settings.HUBSPOT_DRY_RUN = False


def _captured_body(mock_post):
    """Pull the ticket body string out of the HubSpot HTTP payload."""
    payload = mock_post.call_args.kwargs["json"]
    [body_field] = [f for f in payload["fields"] if f["name"] == "ticket.content"]
    return body_field["value"]


def _ok_response():
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"inlineMessage": "ok"}
    return response


@patch("requests.post")
def test_body_contains_user_identity_only(mock_post):
    """Ticket body has just name/email — support runs
    show_deletion_blockers separately for details."""
    mock_post.return_value = _ok_response()
    user = mixer.blend(User, email="x@example.com")

    create_account_deletion_ticket(user)

    body = _captured_body(mock_post)
    assert "x@example.com" in body
    assert "Undeletable data" not in body


@patch("requests.post")
def test_returns_false_when_user_has_no_email(mock_post):
    user = User(email="")
    assert create_account_deletion_ticket(user) is False
    mock_post.assert_not_called()


@override_settings(HUBSPOT_DRY_RUN=True)
@patch("requests.post")
def test_dry_run_skips_http_call_and_returns_success(mock_post):
    """Local dev toggle: HUBSPOT_DRY_RUN=True returns success without
    touching the network, so the blocked self-delete path can be
    exercised end-to-end without filing real support tickets."""
    user = mixer.blend(User, email="dev@example.com")
    assert create_account_deletion_ticket(user) is True
    mock_post.assert_not_called()
