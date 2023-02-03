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

from unittest.mock import patch

import pytest
from django.db import DatabaseError
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture
def healthz_url():
    return reverse("terraso_core:healthz")


def test_get_health_success(client, healthz_url):
    response = client.get(healthz_url)

    assert response.status_code == 200


@patch("apps.core.views.check_db_access")
def test_get_health_with_db_error(mocked_check_db_access, client, healthz_url):
    mocked_check_db_access.side_effect = DatabaseError("Mocked exception!")

    response = client.get(healthz_url)

    assert response.status_code == 400
    assert "Database error" in response.content.decode()


@patch("apps.core.views.check_db_access")
def test_get_health_with_unexpected_error(mocked_check_db_access, client, healthz_url):
    mocked_check_db_access.side_effect = Exception("Mocked exception!")

    response = client.get(healthz_url)

    assert response.status_code == 400
    assert "Unexpected error" in response.content.decode()
