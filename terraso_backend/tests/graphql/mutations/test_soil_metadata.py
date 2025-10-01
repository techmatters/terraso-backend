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
# TODO-cknipe: Wait should we just be sending the userRatings? Should we just be sending a new one? How does GraphQL even work ><
UPDATE_SOIL_METADATA_WITH_USER_RATINGS_QUERY = """
    mutation SoilMetadataUpdateMutation($input: SoilMetadataUpdateMutationInput!) {
        updateSoilMetadata(input: $input) {
            soilMetadata {
                selectedSoilId
                userRatings {
                    soilMatchId
                    rating
                }
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


def test_update_soil_metadata_with_user_ratings_new_client(client, user, site):
    """Test that new clients can use user_ratings field to update ratings"""
    client.force_login(user)
    new_data = {
        "siteId": str(site.id),
        "userRatings": [
            {"soilMatchId": "soil_match_123", "rating": "SELECTED"},
            {"soilMatchId": "soil_match_456", "rating": "REJECTED"},
        ],
    }
    response = graphql_query(
        UPDATE_SOIL_METADATA_WITH_USER_RATINGS_QUERY,
        variables={"input": new_data},
        client=client,
    )
    assert response.json()["data"]["updateSoilMetadata"]["errors"] is None
    payload = response.json()["data"]["updateSoilMetadata"]["soilMetadata"]

    # Check backwards compatible selectedSoilId is set correctly
    assert payload["selectedSoilId"] == "soil_match_123"

    # Check userRatings are set correctly
    user_ratings = payload["userRatings"]
    assert len(user_ratings) == 2

    ratings_dict = {r["soilMatchId"]: r["rating"] for r in user_ratings}
    assert ratings_dict["soil_match_123"] == "SELECTED"
    assert ratings_dict["soil_match_456"] == "REJECTED"


def test_update_soil_metadata_old_client_syncs_to_user_ratings(client, user, site):
    """Test that old clients using selectedSoilId still work and sync to user_ratings"""
    client.force_login(user)

    # Old client sets selectedSoilId
    old_client_data = {
        "siteId": str(site.id),
        "selectedSoilId": "soil_match_789",
    }
    response = graphql_query(
        UPDATE_SOIL_METADATA_WITH_USER_RATINGS_QUERY,
        variables={"input": old_client_data},
        client=client,
    )
    assert response.json()["data"]["updateSoilMetadata"]["errors"] is None
    payload = response.json()["data"]["updateSoilMetadata"]["soilMetadata"]

    # Check it appears in selectedSoilId (backwards compatibility)
    assert payload["selectedSoilId"] == "soil_match_789"

    # Check it was synced to user_ratings
    user_ratings = payload["userRatings"]
    assert len(user_ratings) == 1
    assert user_ratings[0]["soilMatchId"] == "soil_match_789"
    assert user_ratings[0]["rating"] == "SELECTED"


def test_update_soil_metadata_multiple_ratings_only_one_selected(client, user, site):
    """Test that only one soil match can be SELECTED at a time"""
    client.force_login(user)

    # First, set soil_match_123 as SELECTED
    data1 = {
        "siteId": str(site.id),
        "userRatings": [
            {"soilMatchId": "soil_match_123", "rating": "SELECTED"},
        ],
    }
    graphql_query(
        UPDATE_SOIL_METADATA_WITH_USER_RATINGS_QUERY,
        variables={"input": data1},
        client=client,
    )

    # Now update with a new SELECTED rating
    data2 = {
        "siteId": str(site.id),
        "userRatings": [
            {"soilMatchId": "soil_match_123", "rating": "REJECTED"},
            {"soilMatchId": "soil_match_456", "rating": "SELECTED"},
        ],
    }
    response = graphql_query(
        UPDATE_SOIL_METADATA_WITH_USER_RATINGS_QUERY,
        variables={"input": data2},
        client=client,
    )

    payload = response.json()["data"]["updateSoilMetadata"]["soilMetadata"]

    # Only soil_match_456 should be selected
    assert payload["selectedSoilId"] == "soil_match_456"

    user_ratings = payload["userRatings"]
    ratings_dict = {r["soilMatchId"]: r["rating"] for r in user_ratings}
    assert ratings_dict["soil_match_123"] == "REJECTED"
    assert ratings_dict["soil_match_456"] == "SELECTED"
