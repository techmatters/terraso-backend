# Copyright © 2023 Technology Matters
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

OAUTH_COOKIE_NAME = "oauth"
OAUTH_COOKIE_MAX_AGE_SECONDS = 300  # 5 minutes

# Session key set by terraso_login() and checked by OAuthAuthorizeState
# to decide whether to flush the session once the OAuth grant completes.
# Scopes the flush so admin / other sessions are not affected.
SESSION_FLAG_OAUTH_LOGIN = "created_via_oauth_login"
