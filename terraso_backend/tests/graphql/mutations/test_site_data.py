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

from decimal import Decimal

import pytest
import structlog
from graphene_django.utils.testing import graphql_query
from mixer.backend.django import mixer

from apps.core.formatters import from_camel_to_snake_case
from apps.core.models import User
from apps.project_management.models.sites import Site
from apps.soil_id.models.soil_data import SoilData
from apps.soil_id.models.soil_data_history import SoilDataHistory
from apps.soil_id.models.soil_metadata import SoilMetadata

pytestmark = pytest.mark.django_db

logger = structlog.get_logger(__name__)

PUSH_USER_DATA_QUERY = """
    mutation PushUserDataMutation($input: UserDataPushInput!) {
        pushUserData(input: $input) {
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
            errors
        }
    }
"""


def test_push_user_data_with_both_soil_data_and_metadata(client, user):
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
        PUSH_USER_DATA_QUERY,
        input_data={
            "soilDataEntries": [{"siteId": str(site.id), "soilData": soil_data_changes}],
            "soilMetadataEntries": [{"siteId": str(site.id), "userRatings": metadata_changes}],
        },
        client=client,
    )

    result = response.json()["data"]["pushUserData"]
    assert result["errors"] is None

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


def test_push_user_data_with_only_soil_data(client, user):
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
        PUSH_USER_DATA_QUERY,
        input_data={"soilDataEntries": [{"siteId": str(site.id), "soilData": soil_data_changes}]},
        client=client,
    )

    result = response.json()["data"]["pushUserData"]
    assert result["errors"] is None

    # Check soil data results
    assert len(result["soilDataResults"]) == 1
    soil_data_result = result["soilDataResults"][0]["result"]
    assert soil_data_result["__typename"] == "SoilDataPushEntrySuccess"

    # Check soil metadata results are null (not provided)
    assert result["soilMetadataResults"] is None

    # Verify database state
    site.refresh_from_db()
    assert site.soil_data.down_slope == "LINEAR"


def test_push_user_data_with_only_soil_metadata(client, user):
    """Test pushing only soil metadata"""
    site = mixer.blend(Site, owner=user)

    metadata_changes = [
        {"soilMatchId": "soil_a", "rating": "SELECTED"},
        {"soilMatchId": "soil_b", "rating": "REJECTED"},
    ]

    client.force_login(user)
    response = graphql_query(
        PUSH_USER_DATA_QUERY,
        input_data={
            "soilMetadataEntries": [{"siteId": str(site.id), "userRatings": metadata_changes}]
        },
        client=client,
    )

    result = response.json()["data"]["pushUserData"]
    assert result["errors"] is None

    # Check soil data results are null (not provided)
    assert result["soilDataResults"] is None

    # Check soil metadata results
    assert len(result["soilMetadataResults"]) == 1
    metadata_result = result["soilMetadataResults"][0]["result"]
    assert metadata_result["__typename"] == "SoilMetadataPushEntrySuccess"

    # Verify database state
    site.refresh_from_db()
    assert site.soil_metadata.user_ratings == {"soil_a": "SELECTED", "soil_b": "REJECTED"}


def test_push_user_data_with_mixed_results(client, user):
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
        PUSH_USER_DATA_QUERY,
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

    result = response.json()["data"]["pushUserData"]
    assert result["errors"] is None

    # Check soil data succeeded
    assert len(result["soilDataResults"]) == 1
    soil_data_result = result["soilDataResults"][0]["result"]
    assert soil_data_result["__typename"] == "SoilDataPushEntrySuccess"

    # Check soil metadata failed
    assert len(result["soilMetadataResults"]) == 1
    metadata_result = result["soilMetadataResults"][0]["result"]
    assert metadata_result["__typename"] == "SoilMetadataPushEntryFailure"
    assert metadata_result["reason"] == "NOT_ALLOWED"


def test_push_user_data_replaces_user_ratings(client, user):
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
        PUSH_USER_DATA_QUERY,
        input_data={"soilMetadataEntries": [{"siteId": str(site.id), "userRatings": new_ratings}]},
        client=client,
    )

    result = response.json()["data"]["pushUserData"]
    assert result["errors"] is None

    # Verify old ratings are gone and only new ratings exist
    site.refresh_from_db()
    assert site.soil_metadata.user_ratings == {"soil_4": "SELECTED", "soil_5": "UNSURE"}


def test_push_user_data_metadata_validation_multiple_selected(client, user):
    """Test that multiple SELECTED ratings are rejected"""
    site = mixer.blend(Site, owner=user)

    invalid_ratings = [
        {"soilMatchId": "soil_1", "rating": "SELECTED"},
        {"soilMatchId": "soil_2", "rating": "SELECTED"},  # Two SELECTED - invalid
    ]

    client.force_login(user)
    response = graphql_query(
        PUSH_USER_DATA_QUERY,
        input_data={
            "soilMetadataEntries": [{"siteId": str(site.id), "userRatings": invalid_ratings}]
        },
        client=client,
    )

    result = response.json()["data"]["pushUserData"]
    assert result["errors"] is None

    # Check that the entry failed with INVALID_DATA
    assert len(result["soilMetadataResults"]) == 1
    metadata_result = result["soilMetadataResults"][0]["result"]
    assert metadata_result["__typename"] == "SoilMetadataPushEntryFailure"
    assert metadata_result["reason"] == "INVALID_DATA"


def test_push_user_data_requires_at_least_one_entry_type(client, user):
    """Test that at least one of soilDataEntries or soilMetadataEntries is required"""
    client.force_login(user)
    response = graphql_query(PUSH_USER_DATA_QUERY, input_data={}, client=client)

    # Should get a validation error
    assert "errors" in response.json()


def test_push_user_data_with_multiple_sites(client, user):
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
        PUSH_USER_DATA_QUERY,
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

    result = response.json()["data"]["pushUserData"]
    assert result["errors"] is None

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


# ----- Soil data changes only ------
# Tests from test_soil_data.py but with the new non-deprecated endpoint
PUSH_SOIL_DATA_QUERY = """
    mutation PushUserDataMutation($input: UserDataPushInput!) {
        pushUserData(input: $input) {
            soilDataResults {
                siteId
                result {
                    __typename
                    ... on SoilDataPushEntryFailure {
                        reason
                    }
                    ... on SoilDataPushEntrySuccess {
                        soilData {
                            slopeAspect
                            downSlope
                            crossSlope
                            bedrock
                            slopeLandscapePosition
                            slopeSteepnessSelect
                            slopeSteepnessPercent
                            slopeSteepnessDegree
                            surfaceCracksSelect
                            surfaceSaltSelect
                            floodingSelect
                            limeRequirementsSelect
                            surfaceStoninessSelect
                            waterTableDepthSelect
                            soilDepthSelect
                            landCoverSelect
                            grazingSelect
                            depthIntervalPreset
                            depthDependentData {
                                depthInterval {
                                    start
                                    end
                                }
                                clayPercent
                                texture
                                rockFragmentVolume
                                colorHue
                                colorValue
                                colorChroma
                                colorPhotoUsed
                                colorPhotoSoilCondition
                                colorPhotoLightingCondition
                                conductivity
                                conductivityTest
                                conductivityUnit
                                structure
                                ph
                                phTestingSolution
                                phTestingMethod
                                soilOrganicCarbon
                                soilOrganicMatter
                                soilOrganicCarbonTesting
                                soilOrganicMatterTesting
                                sodiumAbsorptionRatio
                                carbonates
                            }
                            depthIntervals {
                                depthInterval {
                                    start
                                    end
                                }
                                label
                                soilTextureEnabled
                                soilColorEnabled
                                carbonatesEnabled
                                phEnabled
                                soilOrganicCarbonMatterEnabled
                                electricalConductivityEnabled
                                sodiumAdsorptionRatioEnabled
                                soilStructureEnabled
                            }
                        }
                    }
                }
            }
            soilMetadataResults {
                siteId
                result {
                    __typename
                    ... on SoilMetadataPushEntryFailure {
                        reason
                    }
                }
            }
            errors
        }
    }
"""


def test_push_soil_data_success(client, user):
    site = mixer.blend(Site, owner=user)

    site.soil_data = SoilData()
    site.soil_data.save()
    site.soil_data.depth_intervals.get_or_create(depth_interval_start=10, depth_interval_end=20)

    soil_data_changes = {
        "slopeAspect": 10,
        "downSlope": "CONVEX",
        "crossSlope": "CONCAVE",
        "bedrock": 20,
        "slopeLandscapePosition": "HILLS_MOUNTAINS",
        "slopeSteepnessSelect": "ROLLING",
        "slopeSteepnessPercent": 15,
        "slopeSteepnessDegree": 30,
        "surfaceCracksSelect": "SURFACE_CRACKING_ONLY",
        "surfaceSaltSelect": "SMALL_TEMPORARY_PATCHES",
        "floodingSelect": "OCCASIONAL",
        "limeRequirementsSelect": "SOME",
        "surfaceStoninessSelect": "BETWEEN_3_AND_15",
        "waterTableDepthSelect": "BETWEEN_30_AND_45_CM",
        "soilDepthSelect": "BETWEEN_50_AND_70_CM",
        "landCoverSelect": "GRASSLAND",
        "grazingSelect": "CATTLE",
        "depthIntervalPreset": "NRCS",
    }

    depth_dependent_changes = {
        "clayPercent": 25,
        "texture": "SANDY_LOAM",
        "rockFragmentVolume": "VOLUME_1_15",
        "colorHue": 7,
        "colorValue": 4,
        "colorChroma": 3,
        "colorPhotoUsed": True,
        "colorPhotoSoilCondition": "MOIST",
        "colorPhotoLightingCondition": "EVEN",
        "conductivity": "2.50",
        "conductivityTest": "SOIL_WATER_1_1",
        "conductivityUnit": "MILLISIEMENS_CENTIMETER",
        "structure": "ANGULAR_BLOCKY",
        "ph": "6.5",
        "phTestingSolution": "SOIL_WATER_1_1",
        "phTestingMethod": "METER",
        "soilOrganicCarbon": "1.2",
        "soilOrganicMatter": "2.3",
        "soilOrganicCarbonTesting": "DRY_COMBUSTION",
        "soilOrganicMatterTesting": "WET_OXIDATION",
        "sodiumAbsorptionRatio": "5.1",
        "carbonates": "SLIGHTLY_EFFERVESCENT",
    }

    depth_interval_changes = {
        "label": "test label",
        "soilTextureEnabled": True,
        "soilColorEnabled": True,
        "carbonatesEnabled": True,
        "phEnabled": True,
        "soilOrganicCarbonMatterEnabled": True,
        "electricalConductivityEnabled": True,
        "sodiumAdsorptionRatioEnabled": True,
        "soilStructureEnabled": True,
    }

    nested_changes = {
        "depthDependentData": [
            {"depthInterval": {"start": 0, "end": 10}, **depth_dependent_changes}
        ],
        "depthIntervals": [
            {
                "depthInterval": {"start": 0, "end": 10},
                **depth_interval_changes,
            }
        ],
        "deletedDepthIntervals": [
            {
                "start": 10,
                "end": 20,
            }
        ],
    }

    client.force_login(user)
    response = graphql_query(
        PUSH_SOIL_DATA_QUERY,
        input_data={
            "soilDataEntries": [
                {"siteId": str(site.id), "soilData": {**soil_data_changes, **nested_changes}},
            ]
        },
        client=client,
    )

    assert response.json()
    result = response.json()["data"]["pushUserData"]
    assert result["errors"] is None
    assert result["soilMetadataResults"] is None  # Not provided

    # Check soil data results
    result_soil_data = result["soilDataResults"][0]["result"]["soilData"]
    for field, expected_value in soil_data_changes.items():
        assert result_soil_data[field] == expected_value
    assert result_soil_data["depthDependentData"][0]["depthInterval"]["start"] == 0
    assert result_soil_data["depthDependentData"][0]["depthInterval"]["end"] == 10
    for field, expected_value in depth_dependent_changes.items():
        assert result_soil_data["depthDependentData"][0][field] == expected_value
    assert result_soil_data["depthIntervals"][0]["depthInterval"]["start"] == 0
    assert result_soil_data["depthIntervals"][0]["depthInterval"]["end"] == 10
    for field, expected_value in depth_interval_changes.items():
        assert result_soil_data["depthIntervals"][0][field] == expected_value
    assert result_soil_data["depthIntervals"][0]["soilTextureEnabled"] is True
    assert len(result_soil_data["depthIntervals"]) == 1

    # Verify database state
    site.refresh_from_db()
    for field, expected_value in soil_data_changes.items():
        assert getattr(site.soil_data, from_camel_to_snake_case(field)) == expected_value
    depth_dependent_data = site.soil_data.depth_dependent_data.get(
        depth_interval_start=0, depth_interval_end=10
    )
    for field, expected_value in depth_dependent_changes.items():
        attr = getattr(depth_dependent_data, from_camel_to_snake_case(field))
        if isinstance(attr, Decimal):
            attr = str(attr)
        assert attr == expected_value
    depth_interval = site.soil_data.depth_intervals.get(
        depth_interval_start=0, depth_interval_end=10
    )
    for field, expected_value in depth_interval_changes.items():
        assert getattr(depth_interval, from_camel_to_snake_case(field)) == expected_value
    assert not site.soil_data.depth_intervals.filter(
        depth_interval_start=10, depth_interval_end=20
    ).exists()

    # Verify history
    history = SoilDataHistory.objects.get(site=site)
    assert history.update_failure_reason is None
    assert history.update_succeeded
    for field, expected_value in soil_data_changes.items():
        assert history.soil_data_changes[from_camel_to_snake_case(field)] == expected_value
    depth_dependent_history = history.soil_data_changes["depth_dependent_data"][0]
    assert depth_dependent_history["depth_interval"]["start"] == 0
    assert depth_dependent_history["depth_interval"]["end"] == 10
    for field, expected_value in depth_dependent_changes.items():
        assert depth_dependent_history[from_camel_to_snake_case(field)] == expected_value
    depth_interval_history = history.soil_data_changes["depth_intervals"][0]
    assert depth_interval_history["depth_interval"]["start"] == 0
    assert depth_interval_history["depth_interval"]["end"] == 10
    for field, expected_value in depth_interval_changes.items():
        assert depth_interval_history[from_camel_to_snake_case(field)] == expected_value


def test_push_user_data_edit_depth_interval(client, user):
    """Test editing depth intervals via pushUserData"""
    site = mixer.blend(Site, owner=user)

    site.soil_data = SoilData()
    site.soil_data.save()
    site.soil_data.depth_intervals.get_or_create(depth_interval_start=0, depth_interval_end=20)

    nested_changes = {
        "depthDependentData": [{"depthInterval": {"start": 1, "end": 10}}],
        "depthIntervals": [
            {
                "depthInterval": {"start": 1, "end": 10},
            }
        ],
        "deletedDepthIntervals": [
            {
                "start": 0,
                "end": 20,
            }
        ],
    }

    client.force_login(user)
    response = graphql_query(
        PUSH_SOIL_DATA_QUERY,
        input_data={
            "soilDataEntries": [
                {"siteId": str(site.id), "soilData": {**nested_changes}},
            ]
        },
        client=client,
    )

    assert response.json()
    assert "data" in response.json()
    result = response.json()["data"]["pushUserData"]
    assert result["errors"] is None
    assert result["soilMetadataResults"] is None  # Not provided
    assert len(result["soilDataResults"]) == 1
    result_soil_data = result["soilDataResults"][0]["result"]["soilData"]

    assert len(result_soil_data["depthIntervals"]) == 1
    assert result_soil_data["depthIntervals"][0]["depthInterval"]["start"] == 1
    assert result_soil_data["depthIntervals"][0]["depthInterval"]["end"] == 10

    # FYI depthDependentData would also maintain the old (0,20) depth interval if
    # it was there to begin with, but it was not
    assert len(result_soil_data["depthDependentData"]) > 0
    assert result_soil_data["depthDependentData"][0]["depthInterval"]["start"] == 1
    assert result_soil_data["depthDependentData"][0]["depthInterval"]["end"] == 10

    # Verify database state
    site.refresh_from_db()
    assert not site.soil_data.depth_intervals.filter(
        depth_interval_start=0, depth_interval_end=20
    ).exists()
    assert site.soil_data.depth_intervals.filter(
        depth_interval_start=1, depth_interval_end=10
    ).exists()

    # Verify history
    history = SoilDataHistory.objects.get(site=site)
    assert history.update_failure_reason is None
    assert history.update_succeeded
    depth_dependent_history = history.soil_data_changes["depth_dependent_data"][0]
    assert depth_dependent_history["depth_interval"]["start"] == 1
    assert depth_dependent_history["depth_interval"]["end"] == 10
    depth_interval_history = history.soil_data_changes["depth_intervals"][0]
    assert depth_interval_history["depth_interval"]["start"] == 1
    assert depth_interval_history["depth_interval"]["end"] == 10


def test_push_user_data_mixed_soil_data_results(client, user):
    """Test that pushUserData can handle mixed success/failure results for soil data"""
    non_user = mixer.blend(User)
    user_sites = mixer.cycle(2).blend(Site, owner=user)
    non_user_site = mixer.blend(Site, owner=non_user)

    client.force_login(user)
    response = graphql_query(
        PUSH_SOIL_DATA_QUERY,
        input_data={
            "soilDataEntries": [
                # update data successfully
                {
                    "siteId": str(user_sites[0].id),
                    "soilData": {
                        "slopeAspect": 10,
                        "depthDependentData": [],
                        "depthIntervals": [],
                        "deletedDepthIntervals": [],
                    },
                },
                # constraint violations
                {
                    "siteId": str(user_sites[1].id),
                    "soilData": {
                        "slopeAspect": -1,
                        "depthDependentData": [],
                        "depthIntervals": [],
                        "deletedDepthIntervals": [],
                    },
                },
                # no permission
                {
                    "siteId": str(non_user_site.id),
                    "soilData": {
                        "slopeAspect": 5,
                        "depthDependentData": [],
                        "depthIntervals": [],
                        "deletedDepthIntervals": [],
                    },
                },
                # does not exist
                {
                    "siteId": "00000000-0000-0000-0000-000000000000",
                    "soilData": {
                        "slopeAspect": 15,
                        "depthDependentData": [],
                        "depthIntervals": [],
                        "deletedDepthIntervals": [],
                    },
                },
            ]
        },
        client=client,
    )

    assert response.json()
    assert "data" in response.json()
    result = response.json()["data"]["pushUserData"]
    assert result["errors"] is None
    assert result["soilMetadataResults"] is None  # Not provided

    # Check results
    assert result["soilDataResults"][0]["result"]["soilData"]["slopeAspect"] == 10
    assert result["soilDataResults"][1]["result"]["reason"] == "INVALID_DATA"
    assert result["soilDataResults"][2]["result"]["reason"] == "NOT_ALLOWED"
    assert result["soilDataResults"][3]["result"]["reason"] == "DOES_NOT_EXIST"

    # Verify database state
    user_sites[0].refresh_from_db()
    assert user_sites[0].soil_data.slope_aspect == 10

    user_sites[1].refresh_from_db()
    assert not hasattr(user_sites[1], "soil_data")

    non_user_site.refresh_from_db()
    assert not hasattr(non_user_site, "soil_data")

    # Verify history
    history_0 = SoilDataHistory.objects.get(site=user_sites[0])
    assert history_0.update_failure_reason is None
    assert history_0.update_succeeded
    assert history_0.soil_data_changes["slope_aspect"] == 10

    history_1 = SoilDataHistory.objects.get(site=user_sites[1])
    assert history_1.update_failure_reason == "INVALID_DATA"
    assert not history_1.update_succeeded
    assert history_1.soil_data_changes["slope_aspect"] == -1

    history_2 = SoilDataHistory.objects.get(site=non_user_site)
    assert history_2.update_failure_reason == "NOT_ALLOWED"
    assert not history_2.update_succeeded
    assert history_2.soil_data_changes["slope_aspect"] == 5

    history_3 = SoilDataHistory.objects.get(site=None)
    assert history_3.update_failure_reason == "DOES_NOT_EXIST"
    assert not history_3.update_succeeded
    assert history_3.soil_data_changes["slope_aspect"] == 15
