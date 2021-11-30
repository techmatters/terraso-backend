import pytest

from apps.core.models import Landscape

pytestmark = pytest.mark.django_db


def test_landscapes_add(client_query):
    landscape_name = "Testing Landscape"
    response = client_query(
        """
        mutation addLandscape($input: LandscapeAddMutationInput!){
          addLandscape(input: $input) {
            landscape {
              id
              name
            }
          }
        }
        """,
        variables={"input": {"name": landscape_name}},
    )
    landscape_result = response.json()["data"]["addLandscape"]["landscape"]

    assert landscape_result["id"]
    assert landscape_result["name"] == landscape_name


def test_landscapes_update(client_query, landscapes):
    old_landscape = _get_landscapes(client_query)[0]
    new_data = {
        "id": old_landscape["id"],
        "description": "New description",
        "name": "New Name",
        "website": "www.example.com/updated-landscape",
    }
    response = client_query(
        """
        mutation updateLandscape($input: LandscapeUpdateMutationInput!) {
          updateLandscape(input: $input) {
            landscape {
              id
              name
              description
              website
            }
          }
        }
        """,
        variables={"input": new_data},
    )
    landscape_result = response.json()["data"]["updateLandscape"]["landscape"]

    assert landscape_result == new_data


def test_landscapes_delete(client_query, landscapes):
    old_landscape = _get_landscapes(client_query)[0]
    response = client_query(
        """
        mutation deleteLandscape($input: LandscapeDeleteMutationInput!){
          deleteLandscape(input: $input) {
            landscape {
              id
              slug
            }
          }
        }

        """,
        variables={"input": {"id": old_landscape["id"]}},
    )

    landscape_result = response.json()["data"]["deleteLandscape"]["landscape"]

    assert landscape_result["slug"] == old_landscape["slug"]
    assert not Landscape.objects.filter(slug=landscape_result["slug"])


def _get_landscapes(client_query):
    response = client_query(
        """
        {
          landscapes {
            edges {
              node {
                id
                slug
              }
            }
          }
        }
        """
    )
    edges = response.json()["data"]["landscapes"]["edges"]
    return [e["node"] for e in edges]
