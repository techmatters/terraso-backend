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


PUSH_SOIL_METADATA_QUERY = """
    mutation PushSoilMetadataMutation($input: SoilMetadataPushInput!) {
        pushSoilMetadata(input: $input) {
            results {
                siteId
                result {
                    __typename
                    ... on SoilMetadataPushEntryFailure {
                        reason
                    }
                    ... on SoilMetadataPushEntrySuccess {
                        soilMetadata {
                            userRatings {
                                soilMatchId
                                rating
                            }
                        }
                    }
                }
            }
            errors
        }
    }
"""


def test_push_soil_metadata_success(client, user, site):
    """Test that pushing soil metadata replaces user_ratings entirely"""
    client.force_login(user)

    # Create existing metadata with some ratings
    SoilMetadata.objects.create(site=site, user_ratings={"soil_1": "UNSURE", "soil_2": "REJECTED"})

    new_data = {
        "soilMetadataEntries": [
            {
                "siteId": str(site.id),
                "soilMetadata": {
                    "userRatings": [
                        {"soilMatchId": "soil_3", "rating": "SELECTED"},
                        {"soilMatchId": "soil_4", "rating": "REJECTED"},
                    ]
                },
            }
        ]
    }

    response = graphql_query(PUSH_SOIL_METADATA_QUERY, input_data=new_data, client=client)

    assert response.json()["data"]["pushSoilMetadata"]["errors"] is None
    result = response.json()["data"]["pushSoilMetadata"]["results"][0]
    assert result["result"]["__typename"] == "SoilMetadataPushEntrySuccess"

    site.refresh_from_db()

    # Verify that user_ratings were completely replaced
    assert site.soil_metadata.user_ratings == {
        "soil_3": "SELECTED",
        "soil_4": "REJECTED",
    }


def test_push_soil_metadata_multiple_selected_fails(client, user, site):
    """Test that multiple SELECTED ratings fail validation"""
    client.force_login(user)

    new_data = {
        "soilMetadataEntries": [
            {
                "siteId": str(site.id),
                "soilMetadata": {
                    "userRatings": [
                        {"soilMatchId": "soil_1", "rating": "SELECTED"},
                        {"soilMatchId": "soil_2", "rating": "SELECTED"},
                    ]
                },
            }
        ]
    }

    response = graphql_query(PUSH_SOIL_METADATA_QUERY, input_data=new_data, client=client)

    result = response.json()["data"]["pushSoilMetadata"]["results"][0]
    assert result["result"]["__typename"] == "SoilMetadataPushEntryFailure"
    assert result["result"]["reason"] == "INVALID_DATA"


def test_push_soil_metadata_not_allowed(client, site):
    """Test that users without permission cannot push soil metadata"""
    unauthorized_user = mixer.blend(User)
    client.force_login(unauthorized_user)

    new_data = {
        "soilMetadataEntries": [
            {
                "siteId": str(site.id),
                "soilMetadata": {
                    "userRatings": [
                        {"soilMatchId": "soil_1", "rating": "SELECTED"},
                    ]
                },
            }
        ]
    }

    response = graphql_query(PUSH_SOIL_METADATA_QUERY, input_data=new_data, client=client)

    result = response.json()["data"]["pushSoilMetadata"]["results"][0]
    assert result["result"]["__typename"] == "SoilMetadataPushEntryFailure"
    assert result["result"]["reason"] == "NOT_ALLOWED"


def test_push_soil_metadata_site_does_not_exist(client, user):
    """Test that pushing to a non-existent site fails"""
    client.force_login(user)

    new_data = {
        "soilMetadataEntries": [
            {
                "siteId": "does-not-exist",
                "soilMetadata": {
                    "userRatings": [
                        {"soilMatchId": "soil_1", "rating": "SELECTED"},
                    ]
                },
            }
        ]
    }

    response = graphql_query(PUSH_SOIL_METADATA_QUERY, input_data=new_data, client=client)

    result = response.json()["data"]["pushSoilMetadata"]["results"][0]
    assert result["result"]["__typename"] == "SoilMetadataPushEntryFailure"
    assert result["result"]["reason"] == "DOES_NOT_EXIST"


def test_push_soil_metadata_multiple_sites(client, user):
    """Test that pushing to multiple sites in one request works correctly"""
    site1 = mixer.blend(Site, owner=user)
    site2 = mixer.blend(Site, owner=user)

    client.force_login(user)

    new_data = {
        "soilMetadataEntries": [
            {
                "siteId": str(site1.id),
                "soilMetadata": {
                    "userRatings": [
                        {"soilMatchId": "soil_1", "rating": "SELECTED"},
                    ]
                },
            },
            {
                "siteId": str(site2.id),
                "soilMetadata": {
                    "userRatings": [
                        {"soilMatchId": "soil_2", "rating": "REJECTED"},
                        {"soilMatchId": "soil_3", "rating": "UNSURE"},
                    ]
                },
            },
        ]
    }

    response = graphql_query(PUSH_SOIL_METADATA_QUERY, input_data=new_data, client=client)

    assert response.json()["data"]["pushSoilMetadata"]["errors"] is None
    results = response.json()["data"]["pushSoilMetadata"]["results"]
    assert len(results) == 2
    assert all(r["result"]["__typename"] == "SoilMetadataPushEntrySuccess" for r in results)

    site1.refresh_from_db()
    site2.refresh_from_db()

    assert site1.soil_metadata.user_ratings == {"soil_1": "SELECTED"}
    assert site2.soil_metadata.user_ratings == {"soil_2": "REJECTED", "soil_3": "UNSURE"}
