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

from types import SimpleNamespace
from unittest import mock

import pytest

from apps.core import analytics

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def reset_client():
    # Each test starts with no cached client.
    analytics._client = None
    yield
    analytics._client = None


def test_is_enabled_requires_flag_and_key(settings):
    settings.POSTHOG_ENABLED = False
    settings.POSTHOG_API_KEY = ""
    assert analytics.is_enabled() is False

    settings.POSTHOG_ENABLED = True
    settings.POSTHOG_API_KEY = ""
    assert analytics.is_enabled() is False

    settings.POSTHOG_ENABLED = False
    settings.POSTHOG_API_KEY = "phc_key"
    assert analytics.is_enabled() is False

    settings.POSTHOG_ENABLED = True
    settings.POSTHOG_API_KEY = "phc_key"
    assert analytics.is_enabled() is True


def test_capture_is_noop_when_disabled(settings):
    settings.POSTHOG_ENABLED = False
    settings.POSTHOG_API_KEY = ""
    with mock.patch.object(analytics, "_get_client") as get_client:
        analytics.capture(distinct_id="user-1", event="session_refreshed")
        get_client.assert_not_called()


def test_capture_skips_when_no_distinct_id(settings):
    settings.POSTHOG_ENABLED = True
    settings.POSTHOG_API_KEY = "phc_key"
    with mock.patch.object(analytics, "_get_client") as get_client:
        analytics.capture(distinct_id=None, event="session_refreshed")
        get_client.assert_not_called()


def test_capture_stamps_source_and_platform(settings):
    settings.POSTHOG_ENABLED = True
    settings.POSTHOG_API_KEY = "phc_key"
    settings.ENV = "staging"
    client = mock.Mock()
    with mock.patch.object(analytics, "_get_client", return_value=client):
        analytics.capture(
            distinct_id="user-1",
            event="soil_id_lookup",
            properties={"status": "matches"},
            set_props={"email": "a@b.org"},
        )
    client.capture.assert_called_once()
    kwargs = client.capture.call_args.kwargs
    assert kwargs["distinct_id"] == "user-1"
    assert kwargs["event"] == "soil_id_lookup"
    assert kwargs["properties"]["source"] == "backend"
    assert kwargs["properties"]["platform"] == "staging"
    assert kwargs["properties"]["status"] == "matches"
    assert kwargs["properties"]["$set"] == {"email": "a@b.org"}


def test_capture_never_raises(settings):
    settings.POSTHOG_ENABLED = True
    settings.POSTHOG_API_KEY = "phc_key"
    client = mock.Mock()
    client.capture.side_effect = RuntimeError("network down")
    with mock.patch.object(analytics, "_get_client", return_value=client):
        # Must swallow the error — analytics can never break a request.
        analytics.capture(distinct_id="user-1", event="session_refreshed")


def test_user_person_properties():
    user = SimpleNamespace(email="Jane@Example.ORG", first_name="Jane", last_name="Doe")
    props = analytics.user_person_properties(user)
    assert props == {
        "email": "Jane@Example.ORG",
        "email_domain": "Example.ORG",
        "name": "Jane Doe",
    }


def test_user_person_properties_omits_blank_name():
    user = SimpleNamespace(email="x@y.org", first_name="", last_name="")
    props = analytics.user_person_properties(user)
    assert props == {"email": "x@y.org", "email_domain": "y.org"}


def test_user_person_properties_none():
    assert analytics.user_person_properties(None) is None
