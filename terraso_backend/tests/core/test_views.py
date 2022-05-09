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
