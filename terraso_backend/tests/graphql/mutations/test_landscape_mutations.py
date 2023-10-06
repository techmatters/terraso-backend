# Copyright © 2021-2023 Technology Matters
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
    json_response = response.json()

    landscape_result = json_response["data"]["addLandscape"]["landscape"]

    assert landscape_result["id"]
    assert landscape_result["name"] == landscape_name

    # Assert user is added as manager
    landscape = Landscape.objects.get(id=landscape_result["id"])
    manager_membership = landscape.membership_list.memberships.first()
    assert manager_membership.user_role == "manager"
    assert manager_membership.user == landscape.created_by


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
            errors
          }
        }
        """,
        variables={"input": {"name": landscape_name}},
    )
    error_result = response.json()["data"]["addLandscape"]["errors"][0]

    assert error_result


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
            errors
          }
        }
        """,
        variables={"input": {"name": landscape_name.upper()}},
    )
    error_result = response.json()["data"]["addLandscape"]["errors"][0]

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
            errors
          }
        }
        """,
        variables={"input": new_data},
    )

    response = response.json()

    assert "errors" in response["data"]["updateLandscape"]
    assert "update_not_allowed" in response["data"]["updateLandscape"]["errors"][0]["message"]


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
            errors
          }
        }

        """,
        variables={"input": {"id": str(old_landscape.id)}},
    )

    response = response.json()

    assert "errors" in response["data"]["deleteLandscape"]
    assert "delete_not_allowed" in response["data"]["deleteLandscape"]["errors"][0]["message"]


def test_landscapes_update_taxonomy_terms(client_query, managed_landscapes):
    old_landscape = managed_landscapes[0]
    new_data = {
        "id": str(old_landscape.id),
        "taxonomyTypeTerms": json.dumps(
            {
                "language": [
                    {
                        "type": "LANGUAGE",
                        "valueOriginal": "an",
                        "valueEn": "Aragonese",
                        "valueEs": "Aragonés",
                    },
                    {
                        "type": "LANGUAGE",
                        "valueOriginal": "eo",
                        "valueEn": "Esperanto",
                        "valueEs": "Esperanto",
                    },
                ]
            }
        ),
    }

    response = client_query(
        """
        mutation updateLandscape($input: LandscapeUpdateMutationInput!) {
          updateLandscape(input: $input) {
            landscape {
              taxonomyTerms {
                edges {
                  node {
                    type
                    valueOriginal
                    valueEs
                    valueEn
                  }
                }
              }
            }
          }
        }
        """,
        variables={"input": new_data},
    )
    landscape_result = response.json()["data"]["updateLandscape"]["landscape"]

    assert landscape_result == {
        "taxonomyTerms": {
            "edges": [
                {
                    "node": {
                        "type": "LANGUAGE",
                        "valueOriginal": "an",
                        "valueEn": "Aragonese",
                        "valueEs": "Aragonés",
                    }
                },
                {
                    "node": {
                        "type": "LANGUAGE",
                        "valueOriginal": "eo",
                        "valueEn": "Esperanto",
                        "valueEs": "Esperanto",
                    }
                },
            ]
        }
    }


def test_landscapes_update_group_associations(client_query, managed_landscapes, groups):
    old_landscape = managed_landscapes[0]
    new_data = {
        "id": str(old_landscape.id),
        "groupAssociations": json.dumps(
            [
                {"slug": groups[0].slug, "partnershipYear": 2012, "isPartnership": True},
                {"slug": groups[1].slug},
                {"slug": groups[2].slug},
            ]
        ),
    }

    response = client_query(
        """
        mutation updateLandscape($input: LandscapeUpdateMutationInput!) {
          updateLandscape(input: $input) {
            landscape {
              associatedGroups(isDefaultLandscapeGroup: false) {
                edges {
                  node {
                    isPartnership
                    partnershipYear
                    group {
                      name
                    }
                  }
                }
              }
            }
          }
        }
        """,
        variables={"input": new_data},
    )
    landscape_result = response.json()["data"]["updateLandscape"]["landscape"]

    def sortedBy(node):
        return node["node"]["group"]["name"]

    expected = [
        {
            "node": {
                "isPartnership": True,
                "partnershipYear": 2012,
                "group": {"name": groups[0].name},
            }
        },
        {
            "node": {
                "isPartnership": False,
                "partnershipYear": None,
                "group": {"name": groups[1].name},
            }
        },
        {
            "node": {
                "isPartnership": False,
                "partnershipYear": None,
                "group": {"name": groups[2].name},
            }
        },
    ].sort(key=sortedBy)

    received = landscape_result["associatedGroups"]["edges"].sort(key=sortedBy)

    assert received == expected


def test_landscapes_update_development_strategy(client_query, managed_landscapes, groups):
    old_landscape = managed_landscapes[0]
    new_data = {
        "id": str(old_landscape.id),
        "developmentStrategy": json.dumps(
            {
                "objectives": "Val1",
                "opportunities": "Val2",
                "problemSitutation": "Val3",
                "interventionStrategy": "Val4",
            }
        ),
    }

    response = client_query(
        """
        mutation updateLandscape($input: LandscapeUpdateMutationInput!) {
          updateLandscape(input: $input) {
            landscape {
              associatedDevelopmentStrategy {
                edges {
                  node {
                    objectives
                    opportunities
                    problemSitutation
                    interventionStrategy
                  }
                }
              }
            }
          }
        }
        """,
        variables={"input": new_data},
    )
    landscape_result = response.json()["data"]["updateLandscape"]["landscape"]

    assert landscape_result == {
        "associatedDevelopmentStrategy": {
            "edges": [
                {
                    "node": {
                        "objectives": "Val1",
                        "opportunities": "Val2",
                        "problemSitutation": "Val3",
                        "interventionStrategy": "Val4",
                    }
                }
            ]
        }
    }


def test_landscape_add_remove_profile_image(client_query, managed_landscapes):
    mutation_query = """
    mutation addProfileImage($input: LandscapeUpdateMutationInput!) {
      updateLandscape(input: $input) {
         landscape {
            id
            profileImage
            profileImageDescription
         }
      }
    }
    """
    landscape_id = str(managed_landscapes[0].pk)
    image_url = "https://example.org/example.jpg"
    image_description = "An example image for you"

    # add profile image
    client_query(
        mutation_query,
        variables={
            "input": {
                "id": landscape_id,
                "profileImage": image_url,
                "profileImageDescription": image_description,
            }
        },
    )
    landscape = Landscape.objects.get(id=landscape_id)
    assert landscape.profile_image == image_url
    assert landscape.profile_image_description == image_description

    # do an unrelated modification to make sure this does not reset image
    client_query(
        mutation_query, variables={"input": {"id": landscape_id, "name": "Profile Image Test"}}
    )
    landscape = Landscape.objects.get(id=landscape_id)
    assert landscape.profile_image == image_url
    assert landscape.profile_image_description == image_description

    # reset profile image
    client_query(
        mutation_query,
        variables={
            "input": {
                "id": landscape_id,
                "profileImage": "",
                "profileImageDescription": "",
            }
        },
    )
    landscape = Landscape.objects.get(id=landscape_id)
    assert landscape.profile_image == ""
    assert landscape.profile_image_description == ""
    # make sure it doesn't change the name too
    assert landscape.name == "Profile Image Test"


def test_landscapes_soft_deleted_can_be_created_again(client_query, managed_landscapes):
    landscape = managed_landscapes[0]
    landscape.delete()
    response = client_query(
        """
        mutation addLandscape($input: LandscapeAddMutationInput!){
          addLandscape(input: $input) {
             landscape {
               name
             }
             errors
          }
        }
        """,
        variables={
            "input": {
                "name": landscape.name,
                "description": landscape.description,
            }
        },
    )
    payload = response.json()
    assert payload["data"]["addLandscape"]["errors"] is None
    assert payload["data"]["addLandscape"]["landscape"]["name"] == landscape.name
