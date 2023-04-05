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

import pytest
from django.urls import reverse
from oauth2_provider.models import Application

pytestmark = pytest.mark.django_db


def test_authorization_template(client, user):
    application = Application(
        name="Test Application",
        redirect_uris=("https://example.org"),
        user=user,
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        algorithm=Application.RS256_ALGORITHM,
        client_secret="1234567890abcdefghijklmnopqrstuvwxyz",
    )
    application.save()
    query_data = {
        "client_id": application.client_id,
        "scope": "openid email",
        "state": "random_state_string",
        "redirect_uri": "https://example.org",
        "response_type": "code",
        "nonce": "nonce",
    }
    url = reverse("oauth2_provider:authorize")
    client.force_login(user)
    resp = client.get(url, query_data)
    assert resp.status_code == 200
    resp.render()
    assert b"Share your name and email" in resp.content
