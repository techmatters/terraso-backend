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

import os

import pandas
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
      management
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

coordinates_to_test = [
    {"latitude": 33.81246789, "longitude": -101.9733687},
    {"latitude": 48, "longitude": -123.38},  # triggered a JSON decoding bug in soil ID cache
    # currently fails upstream
    # {"latitude": 37.430296, "longitude": -122.126583},  noqa: E800
]

DATA_BASED_MATCHES_QUERY = (
    """
  query dataBasedSoilMatches($latitude: Float!, $longitude: Float!, $data: SoilIdInputData!) {
    soilId {
      dataBasedSoilMatches(latitude: $latitude, longitude: $longitude, data: $data) {
        ...dataBasedSoilMatches
        ... on SoilIdFailure {
          reason
        }
      }
    }
  }
  fragment dataBasedSoilMatches on DataBasedSoilMatches {
    dataRegion
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


@pytest.mark.integration
@pytest.mark.parametrize("coords", coordinates_to_test)
def test_us_integration(client, coords):
    # run it twice to exercise the cache
    for _ in range(0, 2):
        response = graphql_query(
            DATA_BASED_MATCHES_QUERY,
            variables={
                "latitude": coords["latitude"],
                "longitude": coords["longitude"],
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

        assert response.json()["data"] is not None
        assert "errors" not in response.json()

        payload = response.json()["data"]["soilId"]["dataBasedSoilMatches"]

        assert "reason" not in payload

        assert payload["dataRegion"] == "US"
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


test_data_df = pandas.read_csv(
    os.path.join(os.path.dirname(__file__), "global_pedon_test_dataset.csv")
)
sampled_ids = ['LY0001', 'CN0059', 'AU0013', 'ES0016', 'JO0018', 'PH0032', 'MZ0058', 'KE0232', 'GA0014', 'IN0047']

random_pedons_df = test_data_df[test_data_df["ID"].isin(sampled_ids)]
pedons = random_pedons_df.groupby("ID")

def transform_texture(texture):
  return texture.upper().replace(" ", "_")

def transform_rfv(rfv):
    if 0 <= rfv < 2:
        return "VOLUME_0_1"
    elif 2 <= rfv < 16:
        return "VOLUME_1_15"
    elif 16 <= rfv < 36:
        return "VOLUME_15_35"
    elif 36 <= rfv < 61:
        return "VOLUME_35_60"
    elif 61 <= rfv <= 100:
        return "VOLUME_60"
    else:
        return None

@pytest.mark.integration
@pytest.mark.parametrize("pedon_id, pedon", pedons)
def test_global_integration(client, pedon_id, pedon):
    depth_dependent_data = []

    for i, row in pedon.iterrows():
        entry = {
            "depthInterval": {
                "start": row["TOPDEP"],
                "end": row["BOTDEP"]
            },
            "texture": transform_texture(row["textClass"]),
            "rockFragmentVolume": transform_rfv(row["RFV"]),
            "colorLAB": {
                "L": row["L"],
                "A": row["A"],
                "B": row["B"]
            }
        }
        depth_dependent_data.append(entry)

    response = graphql_query(
        DATA_BASED_MATCHES_QUERY,
        variables={
            "latitude": pedon["Y_LatDD"].values[0],
            "longitude": pedon["X_LonDD"].values[0],
            "data": {
                "depthDependentData": depth_dependent_data,
            },
        },
        client=client,
    )

    assert response.json()["data"] is not None
    assert "errors" not in response.json()

    payload = response.json()["data"]["soilId"]["dataBasedSoilMatches"]

    assert "reason" not in payload
    assert payload["dataRegion"] == "GLOBAL"

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
        assert info["soilData"] is not None
        assert len(info["soilData"]["depthDependentData"]) > 0
