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

from corsheaders.signals import check_request_enabled


def cors_allow_export_urls(sender, request, **kwargs):
    """
    Enable CORS for token-based export URLs only.

    Token-based exports (/export/token/*) allow public access via bearer tokens,
    so they need CORS enabled for all origins.

    ID-based exports (/export/id/*) require JWT authentication and follow
    the standard CORS policy (CORS_ORIGIN_WHITELIST), so they return False here
    to let the default CORS middleware behavior apply.

    This handler is called by django-cors-headers middleware to determine
    if CORS should be enabled for a particular request.

    Returns:
        bool: True if CORS should be enabled (for /export/token/* URLs), False otherwise
    """
    return request.path.startswith("/export/token/")


# Connect the signal handler
check_request_enabled.connect(cors_allow_export_urls)
