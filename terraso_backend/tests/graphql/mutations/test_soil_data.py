# Copyright © 2023 Technology Matters
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
from decimal import Decimal

import pytest
import structlog
from graphene_django.utils.testing import graphql_query
from mixer.backend.django import mixer
from tests.utils import match_json

from apps.core.formatters import from_camel_to_snake_case
from apps.core.models import User
from apps.project_management.models.projects import Project
from apps.project_management.models.sites import Site
from apps.soil_id.models import (
    DepthIntervalPreset,
    ProjectSoilSettings,
    SoilData,
    SoilDataDepthInterval,
)
from apps.soil_id.models.soil_data_history import SoilDataHistory

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
        "colorHue": 1.5,
        "colorValue": 5.0,
        "colorChroma": 4.5,
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
        ("colorHue", -0.5, "min_value"),
        ("colorHue", 100.5, "max_value"),
        ("colorValue", -0.5, "min_value"),
        ("colorValue", 10.5, "max_value"),
        ("colorChroma", -0.5, "min_value"),
        ("colorChroma", 50.5, "max_value"),
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
    project.soil_settings = ProjectSoilSettings(depth_interval_preset=DepthIntervalPreset.CUSTOM)
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


@pytest.mark.parametrize("preset", ["NRCS", "BLM", "NONE"])
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
        "depthIntervalPreset": "BLM",
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
    assert intervals == []
    new_data.pop("projectId")
    assert payload == new_data


def test_project_soil_settings_defaults(client, project_manager, project):
    client.force_login(project_manager)

    expected_defaults = {
        "depthIntervalPreset": "NRCS",
        "soilPitRequired": True,
        "slopeRequired": True,
        "soilTextureRequired": True,
        "soilColorRequired": True,
        "verticalCrackingRequired": False,
        "carbonatesRequired": False,
        "phRequired": False,
        "soilOrganicCarbonMatterRequired": False,
        "electricalConductivityRequired": False,
        "sodiumAdsorptionRatioRequired": False,
        "soilStructureRequired": False,
        "landUseLandCoverRequired": False,
        "soilLimitationsRequired": False,
        "photosRequired": False,
        "notesRequired": False,
    }

    response = graphql_query(
        UPDATE_PROJECT_SETTINGS_QUERY,
        variables={"input": {"projectId": str(project.id)}},
        client=client,
    )

    assert response.json()["data"]["updateProjectSoilSettings"]["errors"] is None
    payload = response.json()["data"]["updateProjectSoilSettings"]["projectSoilSettings"]
    intervals = payload.pop("depthIntervals")
    assert intervals == []
    assert payload == expected_defaults


@pytest.mark.parametrize("depth_interval_preset", ["NRCS", "BLM", "CUSTOM"])
def test_update_project_depth_interval_preset_depth_dependent_data(
    depth_interval_preset, client, project, project_manager, site_with_soil_data
):
    input_data = {
        "projectId": str(project.id),
        "depthIntervalPreset": depth_interval_preset,
    }
    client.force_login(project_manager)
    assert site_with_soil_data.soil_data.depth_dependent_data.exists()
    response = graphql_query(UPDATE_PROJECT_SETTINGS_QUERY, input_data=input_data, client=client)
    payload = response.json()
    assert "errors" not in payload
    intervals = match_json("*..depthIntervals", payload)
    expected_intervals = []
    assert intervals[0] == expected_intervals
    # make sure soil data was handled correctly
    project.refresh_from_db()
    assert project.soil_settings.depth_interval_preset == depth_interval_preset
    site_with_soil_data.refresh_from_db()
    assert not project.soil_settings.depth_intervals.exists()

    # TODO: This will probably be reimplemented later
    # if original_preset == depth_interval_preset:                               noqa: E800
    #    assert site_with_soil_data.soil_data.depth_dependent_data.exists()      noqa: E800
    # else:                                                                      noqa: E800
    #    assert not site_with_soil_data.soil_data.depth_dependent_data.exists()  noqa: E800


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


APPLY_TO_ALL_QUERY = """
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
                    soilTextureEnabled
                }
            }
            errors
        }
    }
"""


def test_apply_to_all(client, project_site, project_manager):
    # create necessary prereqs
    soil_data = SoilData.objects.create(site=project_site, depth_interval_preset="CUSTOM")
    mixer.blend(ProjectSoilSettings, project=project_site.project, depth_interval_preset="NONE")
    existing_interval = SoilDataDepthInterval.objects.create(
        soil_data=soil_data, depth_interval_start=5, depth_interval_end=6
    )

    apply_all_intervals = [{"start": 1, "end": 5}, {"start": 6, "end": 7}]
    client.force_login(project_manager)
    response = graphql_query(
        APPLY_TO_ALL_QUERY,
        input_data={
            "siteId": str(project_site.id),
            "depthInterval": {
                "start": existing_interval.depth_interval_start,
                "end": existing_interval.depth_interval_end,
            },
            "applyToIntervals": apply_all_intervals,
            "soilTextureEnabled": True,
        },
        client=client,
    ).json()
    assert match_json("*..errors", response) == [None]
    intervals = match_json("*..depthIntervals", response)[0]
    assert len(intervals) == 3
    for interval in intervals:
        assert interval["soilTextureEnabled"]
    db_intervals = SoilDataDepthInterval.objects.filter(soil_data=project_site.soil_data).all()
    for interval in db_intervals:
        assert interval.soil_texture_enabled


PUSH_SOIL_DATA_QUERY = """
    mutation PushSoilDataMutation($input: SoilDataPushInput!) {
        pushSoilData(input: $input) {
            results {
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
                            depthIntervalPreset
                            slopeLandscapePosition
                            slopeAspect
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
                            depthDependentData {
                                depthInterval {
                                    start
                                    end
                                }
                                texture
                                rockFragmentVolume
                                clayPercent
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
                                label
                                depthInterval {
                                  start
                                  end
                                }
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
    result = response.json()["data"]["pushSoilData"]
    assert result["errors"] is None
    result_soil_data = result["results"][0]["result"]["soilData"]
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


def test_push_soil_data_success_on_edit_depth_interval(client, user):
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
    result = response.json()["data"]["pushSoilData"]
    assert result["errors"] is None
    assert len(result["results"]) == 1
    result_soil_data = result["results"][0]["result"]["soilData"]

    assert len(result_soil_data["depthIntervals"]) == 1
    assert result_soil_data["depthIntervals"][0]["depthInterval"]["start"] == 1
    assert result_soil_data["depthIntervals"][0]["depthInterval"]["end"] == 10

    # FYI depthDependentData would also maintain the old (0,20) depth interval if
    # it was there to begin with, but it was not
    assert len(result_soil_data["depthDependentData"]) > 0
    assert result_soil_data["depthDependentData"][0]["depthInterval"]["start"] == 1
    assert result_soil_data["depthDependentData"][0]["depthInterval"]["end"] == 10

    site.refresh_from_db()

    assert not site.soil_data.depth_intervals.filter(
        depth_interval_start=0, depth_interval_end=20
    ).exists()
    assert site.soil_data.depth_intervals.filter(
        depth_interval_start=1, depth_interval_end=10
    ).exists()

    history = SoilDataHistory.objects.get(site=site)
    assert history.update_failure_reason is None
    assert history.update_succeeded
    depth_dependent_history = history.soil_data_changes["depth_dependent_data"][0]
    assert depth_dependent_history["depth_interval"]["start"] == 1
    assert depth_dependent_history["depth_interval"]["end"] == 10
    depth_interval_history = history.soil_data_changes["depth_intervals"][0]
    assert depth_interval_history["depth_interval"]["start"] == 1
    assert depth_interval_history["depth_interval"]["end"] == 10


def test_push_soil_data_can_process_mixed_results(client, user):
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
    result = response.json()["data"]["pushSoilData"]
    assert result["errors"] is None
    assert result["results"][0]["result"]["soilData"]["slopeAspect"] == 10
    assert result["results"][1]["result"]["reason"] == "INVALID_DATA"
    assert result["results"][2]["result"]["reason"] == "NOT_ALLOWED"
    assert result["results"][3]["result"]["reason"] == "DOES_NOT_EXIST"

    user_sites[0].refresh_from_db()
    assert user_sites[0].soil_data.slope_aspect == 10

    user_sites[1].refresh_from_db()
    assert not hasattr(user_sites[1], "soil_data")

    non_user_site.refresh_from_db()
    assert not hasattr(non_user_site, "soil_data")

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
