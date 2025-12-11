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
