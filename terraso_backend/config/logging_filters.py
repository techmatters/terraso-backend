# Copyright © 2021-2025 Technology Matters
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

import logging
import re


class HealthCheckFilter(logging.Filter):
    """
    Filter out successful healthz request logs to reduce log noise.

    Health checks run every 5 seconds (~17,000/day) and clutter the logs.
    This filter removes healthz logs unless they indicate an error (non-200 status).
    """

    def filter(self, record):
        # If not a structlog dict message, keep it
        if not isinstance(record.msg, dict):
            return True

        request = record.msg.get("request", "")
        code = record.msg.get("code")

        # If it's a healthz request and succeeded (200) or has no code (request_started), filter it out
        if "/healthz" in request:
            if code is None or code == 200:
                return False

        return True


# Match a sensitive query parameter (OAuth `code` or any `*_token`) anchored at
# the start of the query string or after `&`, so we don't match substrings like
# `decode=` or `barcode=`. Value runs to the next `&` (or end of string).
_SENSITIVE_QS_RE = re.compile(
    r"((?:^|&)(?:code|\w*_token))=[^&]*",
    re.IGNORECASE,
)


def _redact_query_string(qs):
    return _SENSITIVE_QS_RE.sub(r"\1=[REDACTED]", qs)


class SensitiveQueryParamFilter(logging.Filter):
    """
    Scrub OAuth authorization codes and token-like query params from logged
    request strings.

    django_structlog's RequestMiddleware emits `request='METHOD /path?qs'`
    verbatim. OAuth callbacks (`/auth/google/callback`, `/auth/apple/callback`,
    `/auth/microsoft/callback`) include `code=<auth_code>` as a query param —
    a short-lived bearer credential that RFC 6749 §10.3 says not to log. This
    filter rewrites those values to `[REDACTED]` before the record reaches a
    handler.

    Redacted keys: `code`, plus anything ending in `_token` (covers
    `id_token`, `access_token`, `refresh_token`, and forward-compatible
    variants).
    """

    def filter(self, record):
        if not isinstance(record.msg, dict):
            return True

        request_str = record.msg.get("request")
        if not isinstance(request_str, str) or "?" not in request_str:
            return True

        prefix, _, qs = request_str.partition("?")
        scrubbed = _redact_query_string(qs)
        if scrubbed != qs:
            record.msg["request"] = f"{prefix}?{scrubbed}"

        return True
