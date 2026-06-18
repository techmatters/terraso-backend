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

"""Tests for `create_account_deletion_ticket` — focused on the body
content sent to HubSpot. The HTTP call itself is mocked; we assert what
the ticket body says so support reps get useful context."""

from unittest.mock import Mock, patch

import pytest
from mixer.backend.django import mixer

from apps.core.hubspot import create_account_deletion_ticket
from apps.core.models import User

pytestmark = pytest.mark.django_db


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
def test_body_omits_blockers_section_when_none_supplied(mock_post):
    """The non-blocked path (UserPreferenceUpdate) doesn't pass blockers
    and the ticket body stays clean."""
    mock_post.return_value = _ok_response()
    user = mixer.blend(User, email="x@example.com")

    create_account_deletion_ticket(user)

    body = _captured_body(mock_post)
    assert "Undeletable data" not in body


@patch("requests.post")
def test_body_includes_blockers_with_qualifier_and_ids(mock_post):
    """Blockers from UserDeleteMutation's catch branch render with
    label + count + truncated IDs so support sees what to clean up."""
    mock_post.return_value = _ok_response()
    user = mixer.blend(User, email="x@example.com")

    blockers = [
        {
            "model": "collaboration.Membership",
            "qualifier": "non-project, approved",
            "field": "user",
            "count": 2,
            "ids": ["aaa", "bbb"],
        },
        {
            "model": "story_map.StoryMap",
            "qualifier": None,
            "field": "created_by",
            "count": 1,
            "ids": ["ccc"],
        },
    ]

    create_account_deletion_ticket(user, blockers=blockers)

    body = _captured_body(mock_post)
    assert "Undeletable data blocking automated deletion:" in body
    # Qualifier appears in parens when set; absent otherwise.
    assert "collaboration.Membership (non-project, approved) (user)" in body
    assert "story_map.StoryMap (created_by)" in body
    # IDs and counts render.
    assert "2 row(s)" in body and "aaa" in body and "bbb" in body
    assert "1 row(s)" in body and "ccc" in body


@patch("requests.post")
def test_body_shows_plus_n_more_when_ids_truncated(mock_post):
    """If a blocker's `ids` is truncated below its `count`, the body
    surfaces an explicit "+N more" so support knows there are extras."""
    mock_post.return_value = _ok_response()
    user = mixer.blend(User, email="x@example.com")

    blockers = [
        {
            "model": "shared_data.DataEntry",
            "qualifier": None,
            "field": "created_by",
            "count": 53,
            "ids": [f"id-{i}" for i in range(50)],
        }
    ]

    create_account_deletion_ticket(user, blockers=blockers)

    body = _captured_body(mock_post)
    assert "53 row(s)" in body
    assert "(+3 more)" in body


@patch("requests.post")
def test_returns_false_when_user_has_no_email(mock_post):
    user = User(email="")
    assert create_account_deletion_ticket(user) is False
    mock_post.assert_not_called()
