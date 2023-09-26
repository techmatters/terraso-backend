import json

import pytest
import structlog
from graphene_django.utils.testing import graphql_query
from mixer.backend.django import mixer

from apps.core.models import User
from apps.project_management.models.sites import Site

pytestmark = pytest.mark.django_db

logger = structlog.get_logger(__name__)

UPDATE_SOIL_DATA_QUERY = """
    mutation SoilDataUpdateMutation($input: SoilDataUpdateMutationInput!) {
        updateSoilData(input: $input) {
            soilData {
                downSlope
                crossSlope
                bedrock
                slopeLandscapePosition
                slopeAspect
                slopeSteepnessSelect
                slopeSteepnessPercent
                slopeSteepnessDegree
            }
            errors
        }
    }
"""


def test_update_soil_data(client, user, site):
    client.force_login(user)
    new_data = {
        "siteId": str(site.id),
        "bedrock": 0,
        "downSlope": "CONVEX",
        "crossSlope": "CONCAVE",
        "slopeLandscapePosition": "HILLS_MOUNTAINS",
        "slopeAspect": 10,
        "slopeSteepnessSelect": "FLAT",
        "slopeSteepnessPercent": 50,
        "slopeSteepnessDegree": 60,
    }
    response = graphql_query(UPDATE_SOIL_DATA_QUERY, variables={"input": new_data}, client=client)
    assert response.json()["data"]["updateSoilData"]["errors"] is None
    payload = response.json()["data"]["updateSoilData"]["soilData"]
    new_data.pop("siteId")
    for attr, value in new_data.items():
        assert payload[attr] == value

    cleared_data = dict({k: None for k in new_data.keys()}, siteId=str(site.id))
    response = graphql_query(
        UPDATE_SOIL_DATA_QUERY, variables={"input": cleared_data}, client=client
    )
    payload = response.json()["data"]["updateSoilData"]["soilData"]
    assert response.json()["data"]["updateSoilData"]["errors"] is None
    for attr in new_data.keys():
        assert payload[attr] is None

    partial_data = {"siteId": str(site.id)}
    response = graphql_query(
        UPDATE_SOIL_DATA_QUERY, variables={"input": partial_data}, client=client
    )
    payload = response.json()["data"]["updateSoilData"]["soilData"]
    assert response.json()["data"]["updateSoilData"]["errors"] is None
    for attr in new_data.keys():
        assert payload[attr] is None


def test_update_soil_data_constraints(client, user, site):
    client.force_login(user)
    invalid_values = [
        ("bedrock", -1, "min_value"),
        ("slopeAspect", -1, "min_value"),
        ("slopeAspect", 360, "max_value"),
        ("slopeSteepnessPercent", -1, "min_value"),
        ("slopeSteepnessDegree", -1, "min_value"),
        ("slopeSteepnessDegree", 91, "max_value"),
        ("slopeSteepnessSelect", "VERY_VERY_STEEP", None),
        ("downSlope", "COVEX", None),
        ("crossSlope", "COCAVE", None),
        ("slopeLandscapePosition", "HILLS", None),
    ]
    for attr, value, msg in invalid_values:
        response = graphql_query(
            UPDATE_SOIL_DATA_QUERY,
            variables={"input": {"siteId": str(site.id), attr: value}},
            client=client,
        )
        if msg is None:
            assert not hasattr(response.json(), "data") and response.json()["errors"] is not None
        else:
            error_msg = response.json()["data"]["updateSoilData"]["errors"][0]["message"]
            assert json.loads(error_msg)[0]["code"] == msg
        assert not hasattr(Site.objects.get(id=site.id), "soil_data")


def test_update_soil_data_not_allowed(client, site):
    user = mixer.blend(User)
    client.force_login(user)
    new_data = {
        "siteId": str(site.id),
        "bedrock": 1,
    }
    response = graphql_query(UPDATE_SOIL_DATA_QUERY, variables={"input": new_data}, client=client)
    error_msg = response.json()["data"]["updateSoilData"]["errors"][0]["message"]
    assert json.loads(error_msg)[0]["code"] == "update_not_allowed"

    assert not hasattr(Site.objects.get(id=site.id), "soil_data")


def test_update_depth_intervals(client, user, site):
    client.force_login(user)

    response = graphql_query(
        UPDATE_SOIL_DATA_QUERY, variables={"input": {"siteId": str(site.id)}}, client=client
    )
    assert response.json()["data"]["updateSoilData"]["errors"] is None
    payload = response.json()["data"]["updateSoilData"]["soilData"]
    assert payload["depthIntervals"] == []

    good_intervals = [{"start": 0, "end": 10}, {"start": 10, "end": 30}]
    response = graphql_query(
        UPDATE_SOIL_DATA_QUERY,
        variables={
            "input": {
                "siteId": str(site.id),
                "depthIntervals": good_intervals,
            }
        },
        client=client,
    )
    assert response.json()["data"]["updateSoilData"]["errors"] is None
    payload = response.json()["data"]["updateSoilData"]["soilData"]
    assert payload["depthIntervals"] == good_intervals

    bad_intervalses = [
        [{"start": 0}],
        [{"end": 10}],
        [0, 10],
        [{"start": 0, "middle": 5, "end": 10}],
        [{"stort": 0, "end": 10}],
        [{"start": 0, "and": 10}],
    ]
    for intervals in bad_intervalses:
        response = graphql_query(
            UPDATE_SOIL_DATA_QUERY,
            variables={
                "input": {
                    "siteId": str(site.id),
                    "depthIntervals": intervals,
                }
            },
            client=client,
        )
        assert response.json()["errors"] is not None

    bad_intervalses = [
        [{"start": -1, "end": 10}],
        [{"start": 0, "end": 201}],
        [{"start": 0, "end": 10}, {"start": 9, "end": 20}],
    ]
    for intervals in bad_intervalses:
        response = graphql_query(
            UPDATE_SOIL_DATA_QUERY,
            variables={
                "input": {
                    "siteId": str(site.id),
                    "depthIntervals": intervals,
                }
            },
            client=client,
        )
        assert response.json()["data"]["updateSoilData"]["errors"] is not None


UPDATE_DEPTH_DEPENDENT_QUERY = """
    mutation SoilDataDepthDependentUpdateMutation(
        $input: DepthDependentSoilDataUpdateMutationInput!
    ) {
        updateDepthDependentSoilData(input: $input) {
            depthDependentSoilData {
                depthInterval {
                  start
                  end
                }
                texture
                rockFragmentVolume
                colorHueSubstep
                colorHue
                colorValue
                colorChroma
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
            errors
        }
    }
"""


def test_update_depth_dependent_soil_data(client, user, site):
    client.force_login(user)
    new_data = {
        "siteId": str(site.id),
        "depthInterval": {
            "start": 0,
            "end": 10,
        },
        "texture": "CLAY",
        "rockFragmentVolume": "VOLUME_0_1",
        "colorHueSubstep": "SUBSTEP_2_5",
        "colorHue": "R",
        "colorValue": "VALUE_3",
        "colorChroma": "CHROMA_5",
        "conductivity": "10.0",
        "conductivityTest": "SATURATED_PASTE",
        "conductivityUnit": "DECISIEMENS_METER",
        "structure": "LENTICULAR",
        "ph": "7.4",
        "phTestingSolution": "SOIL_WATER_1_1",
        "phTestingMethod": "METER",
        "soilOrganicCarbon": "43.4",
        "soilOrganicMatter": "57.9",
        "soilOrganicCarbonTesting": "DRY_COMBUSTION",
        "soilOrganicMatterTesting": "OTHER",
        "sodiumAbsorptionRatio": "47.1",
        "carbonates": "NONEFFERVESCENT",
    }
    response = graphql_query(
        UPDATE_DEPTH_DEPENDENT_QUERY, variables={"input": new_data}, client=client
    )
    payload = response.json()["data"]["updateDepthDependentSoilData"]["depthDependentSoilData"]
    assert response.json()["data"]["updateDepthDependentSoilData"]["errors"] is None
    new_data.pop("siteId")
    for attr, value in new_data.items():
        assert payload[attr] == value
    new_data.pop("depthInterval")

    cleared_data = dict(
        {k: None for k in new_data.keys()},
        siteId=str(site.id),
        depthInterval={"start": 0, "end": 10},
    )
    response = graphql_query(
        UPDATE_DEPTH_DEPENDENT_QUERY, variables={"input": cleared_data}, client=client
    )
    payload = response.json()["data"]["updateDepthDependentSoilData"]["depthDependentSoilData"]
    assert response.json()["data"]["updateDepthDependentSoilData"]["errors"] is None
    for attr in new_data.keys():
        assert payload[attr] is None

    partial_data = {"siteId": str(site.id), "depthInterval": {"start": 0, "end": 10}}
    response = graphql_query(
        UPDATE_DEPTH_DEPENDENT_QUERY, variables={"input": partial_data}, client=client
    )
    payload = response.json()["data"]["updateDepthDependentSoilData"]["depthDependentSoilData"]
    assert response.json()["data"]["updateDepthDependentSoilData"]["errors"] is None
    for attr in new_data.keys():
        assert payload[attr] is None


def test_update_depth_dependent_soil_data_constraints(client, user, site):
    client.force_login(user)
    invalid_values = [
        ("texture", "SANDY_SAND", None),
        ("rockFragmentVolume", "VOLUME_0", None),
        ("colorHueSubstep", "SUBSET_2", None),
        ("colorHue", "RY", None),
        ("colorValue", "VALUE_3_5", None),
        ("colorChroma", "CHROMA_9", None),
        ("conductivity", "-1", "min_value"),
        ("conductivity", "10.013", "max_decimal_places"),
        ("conductivityTest", "SOIL_WATER_2_1", None),
        ("conductivityUnit", "CENTISIEMENS_METER", None),
        ("structure", "PRISMATICULAR", None),
        ("ph", "-0.5", "min_value"),
        ("ph", "14.1", "max_value"),
        ("ph", "3.73", "max_decimal_places"),
        ("phTestingSolution", "SOIL_WATER_2_1", None),
        ("phTestingMethod", "INDICATOR_METER", None),
        ("soilOrganicCarbon", "-0.1", "min_value"),
        ("soilOrganicCarbon", "100.1", "max_value"),
        ("soilOrganicCarbon", "54.43", "max_decimal_places"),
        ("soilOrganicMatter", "-0.1", "min_value"),
        ("soilOrganicMatter", "100.1", "max_value"),
        ("soilOrganicMatter", "54.43", "max_decimal_places"),
        ("soilOrganicCarbonTesting", "DRY_OXIDATION", None),
        ("soilOrganicMatterTesting", "WET_COMBUSTION", None),
        ("sodiumAbsorptionRatio", "-0.1", "min_value"),
        ("sodiumAbsorptionRatio", "43234.43", "max_decimal_places"),
        ("carbonates", "EFFERVESCENT", None),
    ]
    for attr, value, msg in invalid_values:
        response = graphql_query(
            UPDATE_DEPTH_DEPENDENT_QUERY,
            variables={
                "input": {
                    "siteId": str(site.id),
                    "depthInterval": {"start": 0, "end": 10},
                    attr: value,
                }
            },
            client=client,
        )
        if msg is None:
            assert not hasattr(response.json(), "data") and response.json()["errors"] is not None
        else:
            error_msg = response.json()["data"]["updateDepthDependentSoilData"]["errors"][0][
                "message"
            ]
            assert json.loads(error_msg)[0]["code"] == msg
        assert not hasattr(Site.objects.get(id=site.id), "soil_data")


def test_update_depth_dependent_soil_data_not_allowed(client, site):
    user = mixer.blend(User)
    client.force_login(user)
    new_data = {
        "siteId": str(site.id),
        "depthInterval": {"start": 0, "end": 10},
        "texture": "CLAY",
    }
    response = graphql_query(
        UPDATE_DEPTH_DEPENDENT_QUERY, variables={"input": new_data}, client=client
    )
    error_msg = response.json()["data"]["updateDepthDependentSoilData"]["errors"][0]["message"]
    assert json.loads(error_msg)[0]["code"] == "update_not_allowed"

    assert not hasattr(Site.objects.get(id=site.id), "soil_data")
