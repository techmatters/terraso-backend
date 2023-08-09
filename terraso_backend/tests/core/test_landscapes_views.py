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

import pytest
from django.urls import reverse
from mixer.backend.django import mixer

from apps.core.models.landscapes import (
    Landscape,
    LandscapeDevelopmentStrategy,
    LandscapeGroup,
    TaxonomyTerm,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def landscape():
    return mixer.blend(
        Landscape,
        id="4c54cf7a-10e0-4442-b48d-acea76c9047c",
        name="Test Landscape",
        description="Test Landscape Description",
        location="EC",
        website="https://www.test-landscape.com",
        email="test@test-landscape.com",
        area_types=["forest", "agriculture"],
        population=1000,
        profile_image="https://www.test-landscape.com/image.jpg",
        profile_image_description="Test Landscape Image Description",
        area_polygon={
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "coordinates": [
                            [
                                [-78.48987855457307, -0.17392947523204327],
                                [-78.48987855457307, -0.19353087386768664],
                                [-78.4779639176145, -0.19353087386768664],
                                [-78.4779639176145, -0.17392947523204327],
                                [-78.48987855457307, -0.17392947523204327],
                            ]
                        ],
                        "type": "Polygon",
                    },
                }
            ],
        },
    )


def test_get_landscape_json_view(client, landscape):
    url = reverse(
        "terraso_core:landscape-export", kwargs={"slug": "test-landscape", "format": "json"}
    )
    response = client.get(url)

    assert response.status_code == 200
    json_response = response.json()
    print(json_response)
    expected = {
        "id": "4c54cf7a-10e0-4442-b48d-acea76c9047c",
        "name": "Test Landscape",
        "description": "Test Landscape Description",
        "region": "EC",
        "publicContactEmail": "test@test-landscape.com",
        "website": "https://www.test-landscape.com",
        "areaTypes": ["forest", "agriculture"],
        "areaScalarHa": 287.4689986,
        "population": 1000,
        "profileImage": "https://www.test-landscape.com/image.jpg",
        "profileImageDescription": "Test Landscape Image Description",
        "areaPolygon": landscape.area_polygon,
        "taxonomyTerms": [],
        "associatedGroups": [],
        "developmentStrategy": None,
    }

    assert json_response["lastUpdated"] is not None

    for key, value in expected.items():
        assert key in json_response, f"Key '{key}' not found in the actual dictionary."
        assert (
            json_response[key] == value
        ), f"Value for key '{key}' does not match. Expected: {value}, Actual: {json_response[key]}"


def test_get_landscape_json_view_groups(client, landscape):
    group = mixer.blend(LandscapeGroup, landscape=landscape, is_default_landscape_group=False)
    url = reverse(
        "terraso_core:landscape-export", kwargs={"slug": "test-landscape", "format": "json"}
    )
    response = client.get(url)

    assert response.status_code == 200
    json_response = response.json()

    assert json_response["associatedGroups"] == [group.group.name]


def test_get_landscape_json_view_terms(client, landscape):
    landscape.taxonomy_terms.add(
        mixer.blend(
            TaxonomyTerm,
            type=TaxonomyTerm.TYPE_ECOSYSTEM_TYPE,
            value_original="Test Term",
            value_en="Test Term en",
            value_es="Test Term es",
        )
    )
    url = reverse(
        "terraso_core:landscape-export", kwargs={"slug": "test-landscape", "format": "json"}
    )
    response = client.get(url)

    assert response.status_code == 200
    json_response = response.json()

    print(json_response["taxonomyTerms"])

    assert json_response["taxonomyTerms"] == [
        {
            "type": "ecosystem-type",
            "value": {
                "original": "Test Term",
                "en": "Test Term en",
                "es": "Test Term es",
            },
        }
    ]


def test_get_landscape_json_view_development_strategy(client, landscape):
    development_strategy = mixer.blend(
        LandscapeDevelopmentStrategy,
        objectives="Test objectives",
        opportunities="Test opportunities",
        problem_situtation="Test problem_situtation",
        intervention_strategy="Test intervention_strategy",
    )
    landscape.associated_development_strategy.add(development_strategy)
    url = reverse(
        "terraso_core:landscape-export", kwargs={"slug": "test-landscape", "format": "json"}
    )
    response = client.get(url)

    assert response.status_code == 200
    json_response = response.json()

    assert json_response["developmentStrategy"] == {
        "objectives": "Test objectives",
        "problemSituation": "Test problem_situtation",
        "interventionStrategy": "Test intervention_strategy",
        "opportunities": "Test opportunities",
    }
