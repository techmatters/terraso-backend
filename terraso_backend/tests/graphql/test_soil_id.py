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


import pytest
import structlog
from graphene_django.utils.testing import graphql_query

pytestmark = pytest.mark.django_db

logger = structlog.get_logger(__name__)

SOIL_MATCH_FRAGMENTS = """
  fragment soilMatch on SoilMatchInfo {
    score
    rank
  }
  fragment soilInfo on SoilInfo {
    soilSeries {
      name
      taxonomySubgroup
      description
      fullDescriptionUrl
    }
    ecologicalSite {
      name
      id
      url
    }
    landCapabilityClass {
      capabilityClass
      subClass
    }
    soilData {
      slope
      depthDependentData {
        depthInterval {
          start
          end
        }
        texture
        rockFragmentVolume
        munsellColorString
      }
    }
  }
"""

LOCATION_BASED_MATCHES_QUERY = (
    """
  query locationBasedSoilMatches($latitude: Float!, $longitude: Float!) {
    soilId {
      locationBasedSoilMatches(latitude: $latitude, longitude: $longitude) {
        ...locationBasedSoilMatches
      }
    }
  }
  fragment locationBasedSoilMatches on LocationBasedSoilMatches {
    matches {
      dataSource
      distanceToNearestMapUnitM
      match {
        ...soilMatch
      }
      soilInfo {
        ...soilInfo
      }
    }
  }
"""
    + SOIL_MATCH_FRAGMENTS
)


def test_location_based_soil_matches_endpoint(client):
    response = graphql_query(
        LOCATION_BASED_MATCHES_QUERY,
        variables={"latitude": 33.81246789, "longitude": -101.9733687},
        client=client,
    )

    assert response.json()["data"] is not None

    payload = response.json()["data"]["soilId"]["locationBasedSoilMatches"]

    assert len(payload["matches"]) > 0

    for match in payload["matches"]:
        assert isinstance(match["dataSource"], str)
        assert isinstance(match["distanceToNearestMapUnitM"], float)

        assert match["match"]["score"] >= 0 and match["match"]["score"] <= 1
        assert match["match"]["rank"] >= 0

        info = match["soilInfo"]

        assert info["soilSeries"] is not None
        assert info["landCapabilityClass"] is not None
        assert info["soilData"] is not None
        assert len(info["soilData"]["depthDependentData"]) > 0


DATA_BASED_MATCHES_QUERY = (
    """
  query dataBasedSoilMatches($latitude: Float!, $longitude: Float!, $data: SoilIdInputData!) {
    soilId {
      dataBasedSoilMatches(latitude: $latitude, longitude: $longitude, data: $data) {
        ...dataBasedSoilMatches
      }
    }
  }
  fragment dataBasedSoilMatches on DataBasedSoilMatches {
    matches {
      dataSource
      distanceToNearestMapUnitM
      locationMatch {
        ...soilMatch
      }
      dataMatch {
        ...soilMatch
      }
      combinedMatch {
        ...soilMatch
      }
      soilInfo {
        ...soilInfo
      }
    }
  }
"""
    + SOIL_MATCH_FRAGMENTS
)


def test_data_based_soil_matches_endpoint(client):
    response = graphql_query(
        DATA_BASED_MATCHES_QUERY,
        variables={
            "latitude": 33.81246789,
            "longitude": -101.9733687,
            "data": {
                "slope": 0.5,
                "depthDependentData": [
                    {
                        "depthInterval": {"start": 0, "end": 10},
                        "texture": "CLAY",
                        "rockFragmentVolume": "VOLUME_0_1",
                        "colorLAB": {"L": 20, "A": 30, "B": 40},
                    }
                ],
            },
        },
        client=client,
    )

    print(response.json())

    assert response.json()["data"] is not None

    payload = response.json()["data"]["soilId"]["dataBasedSoilMatches"]

    assert len(payload["matches"]) > 0

    for match in payload["matches"]:
        assert isinstance(match["dataSource"], str)
        assert isinstance(match["distanceToNearestMapUnitM"], float)

        match_kinds = ["locationMatch", "dataMatch", "combinedMatch"]
        for kind in match_kinds:
            assert match[kind]["score"] >= 0 and match[kind]["score"] <= 1
            assert match[kind]["rank"] >= 0

        info = match["soilInfo"]

        assert info["soilSeries"] is not None
        assert info["landCapabilityClass"] is not None
        assert info["soilData"] is not None
        assert len(info["soilData"]["depthDependentData"]) > 0
