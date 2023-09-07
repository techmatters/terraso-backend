import json

import pytest
import structlog
from graphene_django.utils.testing import graphql_query

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


def test_update_soil_data(client, project_manager, site):
    site.add_owner(project_manager)
    client.force_login(project_manager)
    new_data = {
        "siteId": str(site.id),
        "bedrock": 1,
        "downSlope": "CONVEX",
        "crossSlope": "CONCAVE",
        "slopeLandscapePosition": "HILLS_MOUNTAINS",
        "slopeSteepnessSelect": "FLAT",
    }
    response = graphql_query(UPDATE_SOIL_DATA_QUERY, variables={"input": new_data}, client=client)
    content = json.loads(response.content)
    logger.info(content)
    payload = content["data"]["updateSoilData"]["soilData"]
    assert content["data"]["updateSoilData"]["errors"] is None
    for attr, value in new_data.items():
        assert payload[attr] == value
