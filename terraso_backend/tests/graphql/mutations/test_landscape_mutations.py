import json

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

    error_message = json.loads(error_result["message"])[0]
    assert error_message["code"] == "unique"
    assert error_message["context"]["field"] == "name"


def test_landscapes_add_duplicated_by_slug(client_query, landscapes):
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
        variables={"input": {"name": landscape_name.upper()}},
    )
    error_result = response.json()["errors"][0]

    assert error_result

    error_message = json.loads(error_result["message"])[0]
    assert error_message["code"] == "unique"
    assert error_message["context"]["field"] == "All"


def test_landscapes_update_by_manager_works(client_query, managed_landscapes):
    old_landscape = managed_landscapes[0]
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


def test_landscapes_update_by_member_fails_due_permission_check(client_query, landscapes):
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

    response = response.json()

    assert "errors" in response
    assert "update_not_allowed" in response["errors"][0]["message"]


def test_landscapes_delete_by_manager(client_query, managed_landscapes):
    old_landscape = managed_landscapes[0]

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


def test_landscapes_delete_by_non_manager(client_query, landscapes):
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

    response = response.json()

    assert "errors" in response
    assert "delete_not_allowed" in response["errors"][0]["message"]
