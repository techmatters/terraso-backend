# Copyright © 2025 Technology Matters
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
import structlog
from graphene_django.utils.testing import graphql_query
from mixer.backend.django import mixer

from apps.core.models import User
from apps.project_management.models.sites import Site
from apps.soil_id.models.soil_data import SoilData
from apps.soil_id.models.soil_metadata import SoilMetadata

pytestmark = pytest.mark.django_db

logger = structlog.get_logger(__name__)

PUSH_SITE_DATA_QUERY = """
    mutation PushSiteDataMutation($input: SiteDataPushInput!) {
        pushSiteData(input: $input) {
            soilDataResults {
                siteId
                result {
                    __typename
                    ... on SoilDataPushEntryFailure {
                        reason
                    }
                    ... on SoilDataPushEntrySuccess {
                        soilData {
                            downSlope
                            crossSlope
                            bedrock
                        }
                    }
                }
            }
            soilDataError
            soilMetadataResults {
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
            soilMetadataError
            errors
        }
    }
"""


def test_push_site_data_with_both_soil_data_and_metadata(client, user):
    """Test pushing both soil data and soil metadata in a single request"""
    site = mixer.blend(Site, owner=user)
    site.soil_data = SoilData()
    site.soil_data.save()

    soil_data_changes = {
        "downSlope": "CONVEX",
        "crossSlope": "CONCAVE",
        "bedrock": 20,
        "depthDependentData": [],
        "depthIntervals": [],
        "deletedDepthIntervals": [],
    }

    metadata_changes = [
        {"soilMatchId": "soil_1", "rating": "SELECTED"},
        {"soilMatchId": "soil_2", "rating": "REJECTED"},
        {"soilMatchId": "soil_3", "rating": "UNSURE"},
    ]

    client.force_login(user)
    response = graphql_query(
        PUSH_SITE_DATA_QUERY,
        input_data={
            "soilDataEntries": [{"siteId": str(site.id), "soilData": soil_data_changes}],
            "soilMetadataEntries": [{"siteId": str(site.id), "userRatings": metadata_changes}],
        },
        client=client,
    )

    result = response.json()["data"]["pushSiteData"]
    assert result["errors"] is None
    assert result["soilDataError"] is None
    assert result["soilMetadataError"] is None

    # Check soil data results
    assert len(result["soilDataResults"]) == 1
    soil_data_result = result["soilDataResults"][0]["result"]
    assert soil_data_result["__typename"] == "SoilDataPushEntrySuccess"
    assert soil_data_result["soilData"]["downSlope"] == "CONVEX"
    assert soil_data_result["soilData"]["crossSlope"] == "CONCAVE"
    assert soil_data_result["soilData"]["bedrock"] == 20

    # Check soil metadata results
    assert len(result["soilMetadataResults"]) == 1
    metadata_result = result["soilMetadataResults"][0]["result"]
    assert metadata_result["__typename"] == "SoilMetadataPushEntrySuccess"
    user_ratings = metadata_result["soilMetadata"]["userRatings"]
    assert len(user_ratings) == 3
    assert {"soilMatchId": "soil_1", "rating": "SELECTED"} in user_ratings
    assert {"soilMatchId": "soil_2", "rating": "REJECTED"} in user_ratings
    assert {"soilMatchId": "soil_3", "rating": "UNSURE"} in user_ratings

    # Verify database state
    site.refresh_from_db()
    assert site.soil_data.down_slope == "CONVEX"
    assert site.soil_data.cross_slope == "CONCAVE"
    assert site.soil_data.bedrock == 20
    assert site.soil_metadata.user_ratings == {
        "soil_1": "SELECTED",
        "soil_2": "REJECTED",
        "soil_3": "UNSURE",
    }


def test_push_site_data_with_only_soil_data(client, user):
    """Test pushing only soil data"""
    site = mixer.blend(Site, owner=user)

    soil_data_changes = {
        "downSlope": "LINEAR",
        "depthDependentData": [],
        "depthIntervals": [],
        "deletedDepthIntervals": [],
    }

    client.force_login(user)
    response = graphql_query(
        PUSH_SITE_DATA_QUERY,
        input_data={"soilDataEntries": [{"siteId": str(site.id), "soilData": soil_data_changes}]},
        client=client,
    )

    result = response.json()["data"]["pushSiteData"]
    assert result["errors"] is None
    assert result["soilDataError"] is None
    assert result["soilMetadataError"] is None

    # Check soil data results
    assert len(result["soilDataResults"]) == 1
    soil_data_result = result["soilDataResults"][0]["result"]
    assert soil_data_result["__typename"] == "SoilDataPushEntrySuccess"

    # Check soil metadata results are null (not provided)
    assert result["soilMetadataResults"] is None

    # Verify database state
    site.refresh_from_db()
    assert site.soil_data.down_slope == "LINEAR"


def test_push_site_data_with_only_soil_metadata(client, user):
    """Test pushing only soil metadata"""
    site = mixer.blend(Site, owner=user)

    metadata_changes = [
        {"soilMatchId": "soil_a", "rating": "SELECTED"},
        {"soilMatchId": "soil_b", "rating": "REJECTED"},
    ]

    client.force_login(user)
    response = graphql_query(
        PUSH_SITE_DATA_QUERY,
        input_data={
            "soilMetadataEntries": [{"siteId": str(site.id), "userRatings": metadata_changes}]
        },
        client=client,
    )

    result = response.json()["data"]["pushSiteData"]
    assert result["errors"] is None
    assert result["soilDataError"] is None
    assert result["soilMetadataError"] is None

    # Check soil data results are null (not provided)
    assert result["soilDataResults"] is None

    # Check soil metadata results
    assert len(result["soilMetadataResults"]) == 1
    metadata_result = result["soilMetadataResults"][0]["result"]
    assert metadata_result["__typename"] == "SoilMetadataPushEntrySuccess"

    # Verify database state
    site.refresh_from_db()
    assert site.soil_metadata.user_ratings == {"soil_a": "SELECTED", "soil_b": "REJECTED"}


def test_push_site_data_with_mixed_results(client, user):
    """Test that one section can succeed while another fails"""
    site = mixer.blend(Site, owner=user)
    other_user = mixer.blend(User)
    other_site = mixer.blend(Site, owner=other_user)

    soil_data_changes = {
        "downSlope": "CONVEX",
        "depthDependentData": [],
        "depthIntervals": [],
        "deletedDepthIntervals": [],
    }

    metadata_changes = [{"soilMatchId": "soil_1", "rating": "SELECTED"}]

    client.force_login(user)
    response = graphql_query(
        PUSH_SITE_DATA_QUERY,
        input_data={
            "soilDataEntries": [
                {"siteId": str(site.id), "soilData": soil_data_changes},  # Should succeed
            ],
            "soilMetadataEntries": [
                {
                    "siteId": str(other_site.id),
                    "userRatings": metadata_changes,
                }  # Should fail (no permission)
            ],
        },
        client=client,
    )

    result = response.json()["data"]["pushSiteData"]
    assert result["errors"] is None
    assert result["soilDataError"] is None
    assert result["soilMetadataError"] is None

    # Check soil data succeeded
    assert len(result["soilDataResults"]) == 1
    soil_data_result = result["soilDataResults"][0]["result"]
    assert soil_data_result["__typename"] == "SoilDataPushEntrySuccess"

    # Check soil metadata failed
    assert len(result["soilMetadataResults"]) == 1
    metadata_result = result["soilMetadataResults"][0]["result"]
    assert metadata_result["__typename"] == "SoilMetadataPushEntryFailure"
    assert metadata_result["reason"] == "NOT_ALLOWED"


def test_push_site_data_replaces_user_ratings(client, user):
    """Test that user ratings are replaced, not merged"""
    site = mixer.blend(Site, owner=user)
    SoilMetadata.objects.create(
        site=site, user_ratings={"soil_1": "SELECTED", "soil_2": "REJECTED", "soil_3": "UNSURE"}
    )

    # New ratings that completely replace the old ones
    new_ratings = [
        {"soilMatchId": "soil_4", "rating": "SELECTED"},
        {"soilMatchId": "soil_5", "rating": "UNSURE"},
    ]

    client.force_login(user)
    response = graphql_query(
        PUSH_SITE_DATA_QUERY,
        input_data={"soilMetadataEntries": [{"siteId": str(site.id), "userRatings": new_ratings}]},
        client=client,
    )

    result = response.json()["data"]["pushSiteData"]
    assert result["errors"] is None
    assert result["soilMetadataError"] is None

    # Verify old ratings are gone and only new ratings exist
    site.refresh_from_db()
    assert site.soil_metadata.user_ratings == {"soil_4": "SELECTED", "soil_5": "UNSURE"}


def test_push_site_data_metadata_validation_multiple_selected(client, user):
    """Test that multiple SELECTED ratings are rejected"""
    site = mixer.blend(Site, owner=user)

    invalid_ratings = [
        {"soilMatchId": "soil_1", "rating": "SELECTED"},
        {"soilMatchId": "soil_2", "rating": "SELECTED"},  # Two SELECTED - invalid
    ]

    client.force_login(user)
    response = graphql_query(
        PUSH_SITE_DATA_QUERY,
        input_data={
            "soilMetadataEntries": [{"siteId": str(site.id), "userRatings": invalid_ratings}]
        },
        client=client,
    )

    result = response.json()["data"]["pushSiteData"]
    assert result["errors"] is None
    assert result["soilMetadataError"] is None

    # Check that the entry failed with INVALID_DATA
    assert len(result["soilMetadataResults"]) == 1
    metadata_result = result["soilMetadataResults"][0]["result"]
    assert metadata_result["__typename"] == "SoilMetadataPushEntryFailure"
    assert metadata_result["reason"] == "INVALID_DATA"


def test_push_site_data_requires_at_least_one_entry_type(client, user):
    """Test that at least one of soilDataEntries or soilMetadataEntries is required"""
    client.force_login(user)
    response = graphql_query(PUSH_SITE_DATA_QUERY, input_data={}, client=client)

    # Should get a validation error
    assert "errors" in response.json()


def test_push_site_data_with_multiple_sites(client, user):
    """Test pushing data for multiple sites in a single mutation"""
    # Create three sites
    site1 = mixer.blend(Site, owner=user)
    site2 = mixer.blend(Site, owner=user)
    site3 = mixer.blend(Site, owner=user)

    # Prepare soil data for sites 1 and 2
    soil_data_changes_1 = {
        "downSlope": "CONVEX",
        "crossSlope": "CONCAVE",
        "bedrock": 20,
        "depthDependentData": [],
        "depthIntervals": [],
        "deletedDepthIntervals": [],
    }

    soil_data_changes_2 = {
        "downSlope": "LINEAR",
        "crossSlope": "LINEAR",
        "bedrock": 30,
        "depthDependentData": [],
        "depthIntervals": [],
        "deletedDepthIntervals": [],
    }

    # Prepare metadata for sites 2 and 3
    metadata_changes_2 = [
        {"soilMatchId": "soil_2a", "rating": "SELECTED"},
        {"soilMatchId": "soil_2b", "rating": "REJECTED"},
    ]

    metadata_changes_3 = [
        {"soilMatchId": "soil_3a", "rating": "UNSURE"},
        {"soilMatchId": "soil_3b", "rating": "REJECTED"},
        {"soilMatchId": "soil_3c", "rating": "SELECTED"},
    ]

    client.force_login(user)
    response = graphql_query(
        PUSH_SITE_DATA_QUERY,
        input_data={
            "soilDataEntries": [
                {"siteId": str(site1.id), "soilData": soil_data_changes_1},
                {"siteId": str(site2.id), "soilData": soil_data_changes_2},
            ],
            "soilMetadataEntries": [
                {"siteId": str(site2.id), "userRatings": metadata_changes_2},
                {"siteId": str(site3.id), "userRatings": metadata_changes_3},
            ],
        },
        client=client,
    )

    result = response.json()["data"]["pushSiteData"]
    assert result["errors"] is None
    assert result["soilDataError"] is None
    assert result["soilMetadataError"] is None

    # Check soil data results (2 entries)
    assert len(result["soilDataResults"]) == 2

    # Verify site 1 soil data
    site1_result = next(r for r in result["soilDataResults"] if r["siteId"] == str(site1.id))
    assert site1_result["result"]["__typename"] == "SoilDataPushEntrySuccess"
    assert site1_result["result"]["soilData"]["downSlope"] == "CONVEX"
    assert site1_result["result"]["soilData"]["bedrock"] == 20

    # Verify site 2 soil data
    site2_result = next(r for r in result["soilDataResults"] if r["siteId"] == str(site2.id))
    assert site2_result["result"]["__typename"] == "SoilDataPushEntrySuccess"
    assert site2_result["result"]["soilData"]["downSlope"] == "LINEAR"
    assert site2_result["result"]["soilData"]["bedrock"] == 30

    # Check soil metadata results (2 entries)
    assert len(result["soilMetadataResults"]) == 2

    # Verify site 2 metadata
    site2_metadata_result = next(
        r for r in result["soilMetadataResults"] if r["siteId"] == str(site2.id)
    )
    assert site2_metadata_result["result"]["__typename"] == "SoilMetadataPushEntrySuccess"
    site2_user_ratings = site2_metadata_result["result"]["soilMetadata"]["userRatings"]
    assert len(site2_user_ratings) == 2
    assert {"soilMatchId": "soil_2a", "rating": "SELECTED"} in site2_user_ratings
    assert {"soilMatchId": "soil_2b", "rating": "REJECTED"} in site2_user_ratings

    # Verify site 3 metadata
    site3_metadata_result = next(
        r for r in result["soilMetadataResults"] if r["siteId"] == str(site3.id)
    )
    assert site3_metadata_result["result"]["__typename"] == "SoilMetadataPushEntrySuccess"
    site3_user_ratings = site3_metadata_result["result"]["soilMetadata"]["userRatings"]
    assert len(site3_user_ratings) == 3
    assert {"soilMatchId": "soil_3a", "rating": "UNSURE"} in site3_user_ratings
    assert {"soilMatchId": "soil_3b", "rating": "REJECTED"} in site3_user_ratings
    assert {"soilMatchId": "soil_3c", "rating": "SELECTED"} in site3_user_ratings

    # Verify database state for all sites
    site1.refresh_from_db()
    assert site1.soil_data.down_slope == "CONVEX"
    assert site1.soil_data.bedrock == 20

    site2.refresh_from_db()
    assert site2.soil_data.down_slope == "LINEAR"
    assert site2.soil_data.bedrock == 30
    assert site2.soil_metadata.user_ratings == {"soil_2a": "SELECTED", "soil_2b": "REJECTED"}

    site3.refresh_from_db()
    assert site3.soil_metadata.user_ratings == {
        "soil_3a": "UNSURE",
        "soil_3b": "REJECTED",
        "soil_3c": "SELECTED",
    }
