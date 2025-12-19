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

"""
CORS handler for export URLs.

When is CORS needed?
--------------------
CORS is ONLY needed when JavaScript running in a browser makes cross-origin
requests (fetch/XMLHttpRequest to a different domain).

CORS is needed for:
  - A website using JavaScript to fetch from /export/token/* URLs

CORS is NOT needed for:
  - Clicking a link to download CSV/JSON (direct browser navigation)
  - Mobile apps making HTTP requests
  - curl, wget, or any server-side code
  - The HTML landing pages (same origin as API)

Security note:
--------------
Enabling CORS for /export/token/* is low risk because the security model
is token-based: anyone with a valid token can access the data regardless
of CORS. The token (a 128-bit UUID) IS the security, not CORS.
"""

from corsheaders.signals import check_request_enabled


def cors_allow_export_urls(sender, request, **kwargs):
    """
    Enable CORS for token-based export URLs only.

    Token-based exports (/export/token/*) allow public access via bearer tokens,
    so they need CORS enabled for all origins.

    ID-based exports (/export/id/*) require JWT authentication and follow
    the standard CORS policy (CORS_ORIGIN_WHITELIST), so they return False here
    to let the default CORS middleware behavior apply.

    Returns:
        bool: True if CORS should be enabled (for /export/token/* URLs), False otherwise
    """
    return request.path.startswith("/export/token/")


# Connect the signal handler
check_request_enabled.connect(cors_allow_export_urls)
