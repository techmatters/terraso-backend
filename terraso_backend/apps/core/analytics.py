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

"""Thin, fail-safe wrapper around PostHog for server-side product analytics.

Every call here is fire-and-forget: analytics must never break a request. When
``POSTHOG_ENABLED`` is false or no API key is configured (dev/test/CI), all
functions are no-ops and the PostHog client is never even constructed.

Conventions (see docs/posthog.md):
- ``distinct_id`` is the Terraso user UUID, matching the mobile client, so backend
  and mobile events land on the same person.
- Every event carries ``source: "backend"`` and ``platform`` = the deploy
  environment (``settings.ENV``), reusing the mobile client's ``platform`` key so
  one PostHog filter spans both sources.
- Person properties (email / email_domain / name) are attached via ``$set``,
  mirroring the mobile client's ``identify()`` call.
"""

import structlog
from django.conf import settings

logger = structlog.get_logger(__name__)

# Lazily-constructed singleton PostHog client. Stays None while analytics is
# disabled or if construction fails (we retry on the next call in that case).
_client = None


def is_enabled() -> bool:
    """True only when analytics is switched on and an API key is present."""
    return bool(getattr(settings, "POSTHOG_ENABLED", False) and settings.POSTHOG_API_KEY)


def _get_client():
    global _client
    if _client is not None:
        return _client
    try:
        from posthog import Posthog

        _client = Posthog(
            project_api_key=settings.POSTHOG_API_KEY,
            host=settings.POSTHOG_HOST,
        )
    except Exception:
        # Never let analytics setup break the app; try again next time.
        logger.exception("posthog_client_init_failed")
        _client = None
    return _client


def capture(distinct_id, event, properties=None, set_props=None):
    """Send one event to PostHog. No-op unless analytics is enabled. Never raises.

    Args:
        distinct_id: the person identifier (Terraso user UUID). Falsy → skipped.
        event: the snake_case event name (reuse mobile's names where they overlap).
        properties: event-specific properties; ``source``/``platform`` are added here.
        set_props: person properties to merge onto the profile via ``$set``.
    """
    if not is_enabled() or not distinct_id:
        return
    try:
        client = _get_client()
        if client is None:
            return
        props = {
            "source": "backend",
            "platform": settings.ENV,
            **(properties or {}),
        }
        if set_props:
            props["$set"] = set_props
        client.capture(distinct_id=str(distinct_id), event=event, properties=props)
    except Exception:
        # Fire-and-forget: a failed capture must never affect the request.
        # NB: structlog reserves the `event` kwarg for the log message, so the
        # event name is passed under a different key.
        logger.exception("posthog_capture_failed", event_name=event)


def user_person_properties(user):
    """Standard person properties for a user, mirroring the mobile client.

    Returns ``{email, email_domain, name}`` (name/email_domain omitted when empty),
    or None if there's no user.
    """
    if user is None:
        return None
    email = getattr(user, "email", "") or ""
    props = {"email": email}
    if "@" in email:
        props["email_domain"] = email.rsplit("@", 1)[-1]
    name = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
    if name:
        props["name"] = name
    return props
