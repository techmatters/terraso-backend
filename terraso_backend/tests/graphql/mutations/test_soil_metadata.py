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
from apps.soil_id.models.soil_metadata import SoilMetadata

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


def test_update_selected_soil_with_prior_ratings(client, user, site):
    """Test that new ratings and existing soil ratings play nice"""
    client.force_login(user)
    SoilMetadata.objects.create(
        site=site, user_ratings={"soil1": "UNSURE", "soil2": "REJECTED", "soil3": "SELECTED"}
    )

    new_data = {"siteId": str(site.id), "selectedSoilId": "soil1"}
    response = graphql_query(
        UPDATE_SOIL_METADATA_QUERY, variables={"input": new_data}, client=client
    )

    assert response.json()["data"]["updateSoilMetadata"]["errors"] is None
    assert (
        response.json()["data"]["updateSoilMetadata"]["soilMetadata"]["selectedSoilId"] == "soil1"
    )

    site.refresh_from_db()

    # Test what's in the model too
    assert site.soil_metadata.get_selected_soil_id() == "soil1"
    assert site.soil_metadata.user_ratings == {
        "soil1": "SELECTED",  # Newly selected
        "soil2": "REJECTED",  # Preserved
        # soil3 removed (no longer selected)
    }


UPDATE_SOIL_METADATA_WITH_RATINGS_MUTATION = """
      mutation SoilMetadataUpdateMutation($input: SoilMetadataUpdateMutationInput!) {
          updateSoilMetadata(input: $input) {
              soilMetadata {
                  userRatings {
                      soilMatchId
                      rating
                  }
              }
              errors
          }
      }
  """


def test_update_user_ratings_single_selected(client, user, site):
    """Test that a single SELECTED rating is allowed"""
    client.force_login(user)
    new_data = {
        "siteId": str(site.id),
        "userRatings": [
            {"soilMatchId": "soil_1", "rating": "SELECTED"},
            {"soilMatchId": "soil_2", "rating": "REJECTED"},
            {"soilMatchId": "soil_3", "rating": "UNSURE"},
        ],
    }
    response = graphql_query(
        UPDATE_SOIL_METADATA_WITH_RATINGS_MUTATION, variables={"input": new_data}, client=client
    )
    assert response.json()["data"]["updateSoilMetadata"]["errors"] is None


def test_update_user_ratings_multiple_selected_fails(client, user, site):
    """Test that multiple SELECTED ratings raise a validation error"""
    client.force_login(user)
    new_data = {
        "siteId": str(site.id),
        "userRatings": [
            {"soilMatchId": "soil_1", "rating": "SELECTED"},
            {"soilMatchId": "soil_2", "rating": "SELECTED"},
            {"soilMatchId": "soil_3", "rating": "REJECTED"},
        ],
    }
    response = graphql_query(
        UPDATE_SOIL_METADATA_WITH_RATINGS_MUTATION, variables={"input": new_data}, client=client
    )
    errors = response.json()["data"]["updateSoilMetadata"]["errors"]
    assert errors is not None
    assert "single selected soil" in errors[0]["message"].lower()


def test_update_user_ratings_with_prior_ratings(client, user, site):
    """Test that new ratings and existing soil ratings play nice"""
    client.force_login(user)
    SoilMetadata.objects.create(
        site=site, user_ratings={"soil_1": "UNSURE", "soil_2": "REJECTED", "soil_3": "SELECTED"}
    )

    new_data = {
        "siteId": str(site.id),
        "userRatings": [
            {"soilMatchId": "soil_1", "rating": "SELECTED"},
            {"soilMatchId": "soil_4", "rating": "REJECTED"},
            {"soilMatchId": "soil_5", "rating": "UNSURE"},
        ],
    }
    response = graphql_query(
        UPDATE_SOIL_METADATA_WITH_RATINGS_MUTATION, variables={"input": new_data}, client=client
    )

    assert response.json()["data"]["updateSoilMetadata"]["errors"] is None

    site.refresh_from_db()

    assert site.soil_metadata.user_ratings == {
        "soil_1": "SELECTED",  # Changed to selected
        "soil_2": "REJECTED",  # Preserved
        # soil_3 removed (no longer selected)
        "soil_4": "REJECTED",  # Added
        "soil_5": "UNSURE",  # added
    }
