import json

import pytest
import structlog
from graphene_django.utils.testing import graphql_query
from mixer.backend.django import mixer
from tests.utils import match_json, to_snake_case

from apps.core.models import User
from apps.project_management.models.projects import Project
from apps.project_management.models.sites import Site
from apps.soil_id.models import (
    LandPKSIntervalDefaults,
    NRCSIntervalDefaults,
    ProjectSoilSettings,
    SoilData,
)

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


UPDATE_SOIL_DATA_DEPTH_INTERVAL_QUERY = """
    mutation SoilDataDepthIntervalUpdateMutation(
        $input: SoilDataUpdateDepthIntervalMutationInput!
    ) {
        updateSoilDataDepthInterval(input: $input) {
            soilData {
                depthIntervals {
                    label
                    depthInterval {
                        start
                        end
                    }
                }
            }
            errors
        }
    }
"""

DELETE_SOIL_DATA_DEPTH_INTERVAL_QUERY = """
    mutation SoilDataDepthIntervalDeleteMutation(
        $input: SoilDataDeleteDepthIntervalMutationInput!
    ) {
        deleteSoilDataDepthInterval(input: $input) {
            soilData {
                depthIntervals {
                    label
                    depthInterval {
                        start
                        end
                    }
                }
            }
            errors
        }
    }
"""


def test_update_depth_intervals(client, user, site):
    client.force_login(user)

    good_interval = {"label": "good", "depthInterval": {"start": 10, "end": 30}}
    response = graphql_query(
        UPDATE_SOIL_DATA_DEPTH_INTERVAL_QUERY,
        variables={
            "input": {
                "siteId": str(site.id),
                **good_interval,
            }
        },
        client=client,
    )
    assert response.json()["data"]["updateSoilDataDepthInterval"]["errors"] is None
    payload = response.json()["data"]["updateSoilDataDepthInterval"]["soilData"]
    assert payload["depthIntervals"] == [good_interval]

    bad_intervals = [
        {"start": -1, "end": 10},
        {"start": 0, "end": 201},
        {"start": 40, "end": 30},
        {"start": 29, "end": 31},
        {"start": 9, "end": 11},
    ]
    for interval in bad_intervals:
        response = graphql_query(
            UPDATE_SOIL_DATA_DEPTH_INTERVAL_QUERY,
            variables={
                "input": {
                    "siteId": str(site.id),
                    "depthInterval": interval,
                }
            },
            client=client,
        )
        assert response.json()["data"]["updateSoilDataDepthInterval"]["errors"] is not None

    good_interval2 = {"start": 0, "end": 10}
    response = graphql_query(
        UPDATE_SOIL_DATA_DEPTH_INTERVAL_QUERY,
        variables={
            "input": {
                "siteId": str(site.id),
                "depthInterval": good_interval2,
            }
        },
        client=client,
    )
    assert response.json()["data"]["updateSoilDataDepthInterval"]["errors"] is None
    payload = response.json()["data"]["updateSoilDataDepthInterval"]["soilData"]
    assert payload["depthIntervals"] == [
        {"label": "", "depthInterval": good_interval2},
        good_interval,
    ]

    response = graphql_query(
        DELETE_SOIL_DATA_DEPTH_INTERVAL_QUERY,
        variables={
            "input": {
                "siteId": str(site.id),
                "depthInterval": good_interval["depthInterval"],
            }
        },
        client=client,
    )
    assert response.json()["data"]["deleteSoilDataDepthInterval"]["errors"] is None
    payload = response.json()["data"]["deleteSoilDataDepthInterval"]["soilData"]
    assert payload["depthIntervals"] == [
        {"label": "", "depthInterval": good_interval2},
    ]


def sample_depth_interval_update(site_id, start, end):
    return dict(
        siteId=str(site_id),
        label="New Label",
        depthInterval={"start": start, "end": end},
        soilTextureEnabled=True,
        soilColorEnabled=False,
        carbonatesEnabled=True,
        phEnabled=True,
        soilOrganicCarbonMatterEnabled=False,
        electricalConductivityEnabled=False,
        sodiumAdsorptionRatioEnabled=False,
        soilStructureEnabled=True,
    )


def test_update_soil_data_depth_interval_update_all(
    client, site_with_depth_intervals, project_manager
):
    first_interval = site_with_depth_intervals.soil_data.depth_intervals.first()
    new_data = sample_depth_interval_update(
        site_with_depth_intervals.id,
        first_interval.depth_interval_start,
        first_interval.depth_interval_end,
    )
    new_data["applyToAll"] = True

    client.force_login(project_manager)
    response = graphql_query(
        UPDATE_SOIL_DATA_DEPTH_INTERVAL_QUERY, variables={"input": new_data}, client=client
    ).json()
    assert "errors" not in response

    # test depth intervals have been updated
    site_with_depth_intervals.refresh_from_db()
    for interval in site_with_depth_intervals.soil_data.depth_intervals.all():
        for key, value in new_data.items():
            key = to_snake_case(key)
            if key in ("site_id", "depth_interval", "apply_to_all"):
                continue
            if key == "label" and interval.id != first_interval.id:
                assert interval.label != new_data["label"]
                continue
            interval_val = getattr(interval, key)
            assert interval_val == value


UPDATE_DEPTH_DEPENDENT_QUERY = """
    mutation SoilDataDepthDependentUpdateMutation(
        $input: DepthDependentSoilDataUpdateMutationInput!
    ) {
        updateDepthDependentSoilData(input: $input) {
            soilData {
                depthDependentData {
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
        "conductivity": "10.00",
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
    assert response.json()["data"]["updateDepthDependentSoilData"]["errors"] is None
    payload = response.json()["data"]["updateDepthDependentSoilData"]["soilData"][
        "depthDependentData"
    ][0]
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
    assert response.json()["data"]["updateDepthDependentSoilData"]["errors"] is None
    payload = response.json()["data"]["updateDepthDependentSoilData"]["soilData"][
        "depthDependentData"
    ][0]
    for attr in new_data.keys():
        assert payload[attr] is None

    partial_data = {"siteId": str(site.id), "depthInterval": {"start": 0, "end": 10}}
    response = graphql_query(
        UPDATE_DEPTH_DEPENDENT_QUERY, variables={"input": partial_data}, client=client
    )
    assert response.json()["data"]["updateDepthDependentSoilData"]["errors"] is None
    payload = response.json()["data"]["updateDepthDependentSoilData"]["soilData"][
        "depthDependentData"
    ][0]
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


UPDATE_PROJECT_DEPTH_INTERVAL_QUERY = """
    mutation ProjectDepthIntervalUpdateMutation(
        $input: ProjectSoilSettingsUpdateDepthIntervalMutationInput!
    ) {
        updateProjectSoilSettingsDepthInterval(input: $input) {
            projectSoilSettings {
                depthIntervals {
                    label
                    depthInterval {
                        start
                        end
                    }
                }
            }
            errors
        }
    }
"""

DELETE_PROJECT_DEPTH_INTERVAL_QUERY = """
    mutation ProjectDepthIntervalDeleteMutation(
        $input: ProjectSoilSettingsDeleteDepthIntervalMutationInput!
    ) {
        deleteProjectSoilSettingsDepthInterval(input: $input) {
            projectSoilSettings {
                depthIntervals {
                    label
                    depthInterval {
                        start
                        end
                    }
                }
            }
            errors
        }
    }
"""


def test_update_project_depth_intervals(client, project_manager, project):
    client.force_login(project_manager)

    # make sure there is no overlap by settings depth interval preset
    project.soil_settings = ProjectSoilSettings(depth_interval_preset="CUSTOM")
    project.soil_settings.save()

    good_interval = {"label": "good", "depthInterval": {"start": 10, "end": 30}}
    response = graphql_query(
        UPDATE_PROJECT_DEPTH_INTERVAL_QUERY,
        variables={
            "input": {
                "projectId": str(project.id),
                **good_interval,
            }
        },
        client=client,
    )
    assert response.json()["data"]["updateProjectSoilSettingsDepthInterval"]["errors"] is None
    payload = response.json()["data"]["updateProjectSoilSettingsDepthInterval"][
        "projectSoilSettings"
    ]
    assert payload["depthIntervals"] == [good_interval]

    bad_intervals = [
        {"start": -1, "end": 10},
        {"start": 0, "end": 201},
        {"start": 40, "end": 30},
        {"start": 29, "end": 31},
        {"start": 9, "end": 11},
    ]
    for interval in bad_intervals:
        response = graphql_query(
            UPDATE_PROJECT_DEPTH_INTERVAL_QUERY,
            variables={
                "input": {
                    "projectId": str(project.id),
                    "depthInterval": interval,
                }
            },
            client=client,
        )
        assert (
            response.json()["data"]["updateProjectSoilSettingsDepthInterval"]["errors"] is not None
        )

    good_interval2 = {"start": 0, "end": 10}
    response = graphql_query(
        UPDATE_PROJECT_DEPTH_INTERVAL_QUERY,
        variables={
            "input": {
                "projectId": str(project.id),
                "depthInterval": good_interval2,
            }
        },
        client=client,
    )
    assert response.json()["data"]["updateProjectSoilSettingsDepthInterval"]["errors"] is None
    payload = response.json()["data"]["updateProjectSoilSettingsDepthInterval"][
        "projectSoilSettings"
    ]
    assert payload["depthIntervals"] == [
        {"label": "", "depthInterval": good_interval2},
        good_interval,
    ]

    response = graphql_query(
        DELETE_PROJECT_DEPTH_INTERVAL_QUERY,
        variables={
            "input": {
                "projectId": str(project.id),
                "depthInterval": good_interval["depthInterval"],
            }
        },
        client=client,
    )
    assert response.json()["data"]["deleteProjectSoilSettingsDepthInterval"]["errors"] is None
    payload = response.json()["data"]["deleteProjectSoilSettingsDepthInterval"][
        "projectSoilSettings"
    ]
    assert payload["depthIntervals"] == [
        {"label": "", "depthInterval": good_interval2},
    ]


@pytest.mark.parametrize("preset", ["LANDPKS", "NRCS", "NONE"])
def test_updating_project_interval_not_allowed_with_preset(
    preset, client, project, project_manager
):
    ProjectSoilSettings.objects.create(project=project, depth_interval_preset=preset)
    input_data = {"projectId": str(project.id), "depthInterval": {"start": 0, "end": 1}}
    client.force_login(project_manager)
    response = graphql_query(
        UPDATE_PROJECT_DEPTH_INTERVAL_QUERY, input_data=input_data, client=client
    ).json()
    errors = match_json("*..errors[0]", response)
    assert errors
    assert "update_not_allowed" in errors[0]["message"]


UPDATE_PROJECT_SETTINGS_QUERY = """
    mutation ProjectSettingsDeleteMutation(
        $input: ProjectSoilSettingsUpdateMutationInput!
    ) {
        updateProjectSoilSettings(input: $input) {
            projectSoilSettings {
                measurementUnits
                depthIntervalPreset
                soilPitRequired
                slopeRequired
                soilTextureRequired
                soilColorRequired
                verticalCrackingRequired
                carbonatesRequired
                phRequired
                soilOrganicCarbonMatterRequired
                electricalConductivityRequired
                sodiumAdsorptionRatioRequired
                soilStructureRequired
                landUseLandCoverRequired
                soilLimitationsRequired
                photosRequired
                notesRequired
                depthIntervals {
                    depthInterval {
                        start
                        end
                    }
                }
            }
            errors
        }
    }
"""


def make_intervals(defs):
    return [
        dict(
            depthInterval=dict(
                start=interval["depth_interval_start"], end=interval["depth_interval_end"]
            )
        )
        for interval in defs
    ]


def test_update_project_soil_settings(client, user, project_manager, project):
    client.force_login(user)

    new_data = {
        "projectId": str(project.id),
        "measurementUnits": "METRIC",
        "depthIntervalPreset": "NRCS",
        "soilPitRequired": True,
        "slopeRequired": False,
        "soilTextureRequired": True,
        "soilColorRequired": True,
        "verticalCrackingRequired": False,
        "carbonatesRequired": True,
        "phRequired": True,
        "soilOrganicCarbonMatterRequired": False,
        "electricalConductivityRequired": True,
        "sodiumAdsorptionRatioRequired": True,
        "soilStructureRequired": True,
        "landUseLandCoverRequired": False,
        "soilLimitationsRequired": True,
        "photosRequired": True,
        "notesRequired": True,
    }

    response = graphql_query(
        UPDATE_PROJECT_SETTINGS_QUERY, variables={"input": new_data}, client=client
    )
    error_msg = response.json()["data"]["updateProjectSoilSettings"]["errors"][0]["message"]
    assert json.loads(error_msg)[0]["code"] == "update_not_allowed"
    assert not hasattr(Project.objects.get(id=project.id), "soil_settings")

    client.force_login(project_manager)

    response = graphql_query(
        UPDATE_PROJECT_SETTINGS_QUERY, variables={"input": new_data}, client=client
    )
    assert response.json()["data"]["updateProjectSoilSettings"]["errors"] is None
    payload = response.json()["data"]["updateProjectSoilSettings"]["projectSoilSettings"]
    intervals = payload.pop("depthIntervals")
    assert intervals == make_intervals(NRCSIntervalDefaults)
    new_data.pop("projectId")
    assert payload == new_data


@pytest.mark.parametrize("depth_interval_preset", ["LANDPKS", "NRCS", "CUSTOM"])
def test_update_project_depth_interval_preset_depth_dependent_data(
    depth_interval_preset, client, project, project_manager, site_with_soil_data
):
    original_preset = project.soil_settings.depth_interval_preset
    input_data = {
        "projectId": str(project.id),
        "depthIntervalPreset": depth_interval_preset,
    }
    client.force_login(project_manager)
    response = graphql_query(UPDATE_PROJECT_SETTINGS_QUERY, input_data=input_data, client=client)
    payload = response.json()
    assert "errors" not in payload
    intervals = match_json("*..depthIntervals", payload)
    expected_intervals = make_intervals(
        {"LANDPKS": LandPKSIntervalDefaults, "NRCS": NRCSIntervalDefaults, "CUSTOM": []}[
            depth_interval_preset
        ]
    )
    assert intervals[0] == expected_intervals
    # make sure soil data was handled correctly
    project.refresh_from_db()
    assert project.soil_settings.depth_interval_preset == depth_interval_preset
    site_with_soil_data.refresh_from_db()
    if depth_interval_preset == "CUSTOM":
        assert not project.soil_settings.depth_intervals.exists()
    else:
        assert project.soil_settings.depth_intervals.exists()
    if original_preset == depth_interval_preset:
        assert site_with_soil_data.soil_data.depth_dependent_data.exists()
    else:
        assert not site_with_soil_data.soil_data.depth_dependent_data.exists()


UPDATE_SOIL_DEPTH_PRESET_GRAPHQL = """
mutation updateSoilPreset($input: SoilDataUpdateDepthPresetMutationInput!) {
  updateSoilDataDepthPreset(input: $input) {
    intervals {
      depthInterval {
        start
        end
      }
    }
  }
}
"""


@pytest.fixture
def permissions_data(request):
    user = mixer.blend(User)
    project = mixer.blend(Project)
    site = mixer.blend(Site, project=project)
    mixer.blend(SoilData, site=site)
    allowed = False
    match request.param:
        case "project_manager":
            project.add_manager(user)
            allowed = True
        case "owner":
            site.add_owner(user)
            allowed = True
        case "project_viewer":
            project.add_viewer(user)
    return allowed, user, site


@pytest.mark.parametrize(
    "preset,expected",
    [
        ("LANDPKS", {"intervals": make_intervals(LandPKSIntervalDefaults)}),
        ("NRCS", {"intervals": make_intervals(NRCSIntervalDefaults)}),
        ("CUSTOM", {"intervals": []}),
    ],
)
@pytest.mark.parametrize(
    "permissions_data",
    ["project_manager", "project_viewer", "owner", "unassociated"],
    indirect=True,
)
def test_change_soil_depth_preset(client, permissions_data, preset, expected):
    allowed, user, site = permissions_data
    input_ = dict(siteId=str(site.id), preset=preset)
    client.force_login(user)
    payload = graphql_query(
        UPDATE_SOIL_DEPTH_PRESET_GRAPHQL, input_data=input_, client=client
    ).json()
    if not allowed:
        assert "errors" in payload
    else:
        assert "errors" not in payload
        assert payload["data"]["updateSoilDataDepthPreset"] == expected
