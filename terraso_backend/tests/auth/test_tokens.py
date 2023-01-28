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

from django.utils import timezone

from apps.auth.oauth2 import Tokens


def test_tokens(access_tokens_google):
    tokens = Tokens.from_google(access_tokens_google)

    assert tokens.access_token
    assert tokens.refresh_token
    assert tokens.expires_at > timezone.now()


def test_tokens_with_openid(access_tokens_google):
    tokens = Tokens.from_google(access_tokens_google)

    open_id = tokens.open_id

    assert open_id
    assert open_id.name == "Testing Terraso"
    assert open_id.given_name == "Testing"
    assert open_id.family_name == "Terraso"
    assert open_id.email == "testingterraso@example.com"
    assert open_id.picture
