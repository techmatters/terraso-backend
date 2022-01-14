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


def test_landscapes_add_has_created_by_filled_out(client_query, users):
    landscape_name = "Testing Landscape"
    landscape_creator = users[0]
    response = client_query(
        """
        mutation addLandscape($input: LandscapeAddMutationInput!){
          addLandscape(input: $input) {
            landscape {
              id
              name
              createdBy { email }
            }
          }
        }
        """,
        variables={"input": {"name": landscape_name}},
    )
    landscape_result = response.json()["data"]["addLandscape"]["landscape"]

    assert landscape_result["id"]
    assert landscape_result["name"] == landscape_name
    assert landscape_result["createdBy"]["email"] == landscape_creator.email


def test_landscapes_add_duplicated(client_query, landscapes):
    landscape_name = landscapes[0].name
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
    error_result = response.json()["errors"][0]

    assert error_result
    assert "field=name" in error_result["message"]


def test_landscapes_update(client_query, landscapes):
    old_landscape = landscapes[0]
    new_data = {
        "id": str(old_landscape.id),
        "description": "New description",
        "name": "New Name",
        "website": "https://www.example.com/updated-landscape",
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
    old_landscape = landscapes[0]
    response = client_query(
        """
        mutation deleteLandscape($input: LandscapeDeleteMutationInput!){
          deleteLandscape(input: $input) {
            landscape {
              slug
            }
          }
        }

        """,
        variables={"input": {"id": str(old_landscape.id)}},
    )

    landscape_result = response.json()["data"]["deleteLandscape"]["landscape"]

    assert landscape_result["slug"] == old_landscape.slug
    assert not Landscape.objects.filter(slug=landscape_result["slug"])
