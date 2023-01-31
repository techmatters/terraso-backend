# Copyright © 2021-2023 Technology Matters
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

import structlog
from django.http.response import JsonResponse

logger = structlog.get_logger(__name__)


class AuthenticationRequiredMixin:
    def get_auth_enabled(self):
        return True

    def dispatch(self, request, *args, **kwargs):
        if self.get_auth_enabled() and not request.user.is_authenticated:
            logger.warning("Unauthenticated request to authentication required resource")
            return JsonResponse({"error": "Unauthenticated request"}, status=401)

        return super().dispatch(request, *args, **kwargs)
