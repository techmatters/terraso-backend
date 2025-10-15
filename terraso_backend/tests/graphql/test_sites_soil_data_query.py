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
from graphene_django.utils.testing import graphql_query
from mixer.backend.django import mixer

from apps.project_management.models import Site
from apps.soil_id.models import SoilData, SoilMetadata

pytestmark = pytest.mark.django_db


def test_query_site_soil_data_fields(client, user):
    site = mixer.blend(Site, owner=user, name="name")
    (SoilData.objects.create(site=site, bedrock=1),)
    # Create SoilMetadata with user_ratings instead of selected_soil_id
    (SoilMetadata.objects.create(site=site, user_ratings={"a": "SELECTED"}),)

    query = """
    {
      site(id: "%s") {
        name
        soilData { bedrock }
        soilMetadata { selectedSoilId }
      }
    }
    """
    client.force_login(user)

    response = graphql_query(query % site.id, client=client)

    assert "errors" not in response.json()
    site_json = response.json()["data"]["site"]
    assert site_json["name"] == site.name
    assert site_json["soilData"] is not None
    assert site_json["soilMetadata"] is not None
    assert site_json["soilData"]["bedrock"] == 1
    assert site_json["soilMetadata"]["selectedSoilId"] == "a"


def test_query_site_soil_metadata_user_ratings(client, user):
    """Test that new user_ratings field works correctly"""
    site = mixer.blend(Site, owner=user, name="name")
    SoilMetadata.objects.create(
        site=site, user_ratings={"soil_match_123": "SELECTED", "soil_match_456": "REJECTED"}
    )

    query = """
    {
      site(id: "%s") {
        soilMetadata {
          selectedSoilId
          userRatings {
            soilMatchId
            rating
          }
        }
      }
    }
    """
    client.force_login(user)

    response = graphql_query(query % site.id, client=client)

    assert "errors" not in response.json()
    metadata = response.json()["data"]["site"]["soilMetadata"]

    # Backwards compatible selectedSoilId should return the SELECTED one
    assert metadata["selectedSoilId"] == "soil_match_123"

    # New userRatings field should contain both ratings
    user_ratings = metadata["userRatings"]
    assert len(user_ratings) == 2

    ratings_dict = {r["soilMatchId"]: r["rating"] for r in user_ratings}
    assert ratings_dict["soil_match_123"] == "SELECTED"
    assert ratings_dict["soil_match_456"] == "REJECTED"


def test_query_site_soil_metadata_no_selection(client, user):
    """Test that selectedSoilId returns null when nothing is selected"""
    site = mixer.blend(Site, owner=user, name="name")
    SoilMetadata.objects.create(site=site, user_ratings={"soil_match_789": "UNSURE"})

    query = """
    {
      site(id: "%s") {
        soilMetadata {
          selectedSoilId
          userRatings {
            soilMatchId
            rating
          }
        }
      }
    }
    """
    client.force_login(user)

    response = graphql_query(query % site.id, client=client)

    assert "errors" not in response.json()
    metadata = response.json()["data"]["site"]["soilMetadata"]

    # No SELECTED rating, so selectedSoilId should be null
    assert metadata["selectedSoilId"] is None

    # But userRatings should still have the UNSURE rating
    assert len(metadata["userRatings"]) == 1
    assert metadata["userRatings"][0]["soilMatchId"] == "soil_match_789"
    assert metadata["userRatings"][0]["rating"] == "UNSURE"
