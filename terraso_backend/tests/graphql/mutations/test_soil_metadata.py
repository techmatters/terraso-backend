# Copyright © 2024 Technology Matters
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

import json

import pytest
import structlog
from graphene_django.utils.testing import graphql_query
from mixer.backend.django import mixer

from apps.core.models import User
from apps.project_management.models.sites import Site

pytestmark = pytest.mark.django_db

logger = structlog.get_logger(__name__)

UPDATE_SOIL_METADATA_QUERY = """
    mutation SoilMetadataUpdateMutation($input: SoilMetadataUpdateMutationInput!) {
        updateSoilMetadata(input: $input) {
            soilMetadata {
                selectedSoilId
            }
            errors
        }
    }
"""


def test_update_soil_metadata(client, user, site):
    client.force_login(user)
    new_data = {
        "siteId": str(site.id),
        "selectedSoilId": "test",
    }
    response = graphql_query(
        UPDATE_SOIL_METADATA_QUERY, variables={"input": new_data}, client=client
    )
    assert response.json()["data"]["updateSoilMetadata"]["errors"] is None
    payload = response.json()["data"]["updateSoilMetadata"]["soilMetadata"]

    assert payload["selectedSoilId"] == "test"


def test_update_soil_metadata_clear(client, user, site):
    client.force_login(user)
    cleared_data = {
        "siteId": str(site.id),
        "selectedSoilId": None,
    }
    response = graphql_query(
        UPDATE_SOIL_METADATA_QUERY, variables={"input": cleared_data}, client=client
    )
    payload = response.json()["data"]["updateSoilMetadata"]["soilMetadata"]
    assert response.json()["data"]["updateSoilMetadata"]["errors"] is None

    assert payload["selectedSoilId"] is None


def test_update_soil_metadata_not_allowed(client, site):
    user = mixer.blend(User)
    client.force_login(user)
    new_data = {
        "siteId": str(site.id),
        "selectedSoilId": None,
    }
    response = graphql_query(
        UPDATE_SOIL_METADATA_QUERY, variables={"input": new_data}, client=client
    )
    error_msg = response.json()["data"]["updateSoilMetadata"]["errors"][0]["message"]
    assert json.loads(error_msg)[0]["code"] == "update_not_allowed"

    assert not hasattr(Site.objects.get(id=site.id), "soil_metadata")
