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

pytestmark = pytest.mark.django_db


def test_landscapes_query(client_query, landscapes):
    response = client_query(
        """
        {landscapes {
          edges {
            node {
              slug
            }
          }
        }}
        """
    )
    edges = response.json()["data"]["landscapes"]["edges"]
    landscapes_result = [edge["node"]["slug"] for edge in edges]

    for landscape in landscapes:
        assert landscape.slug in landscapes_result


def test_landscape_get_one_by_id(client_query, landscapes):
    landscape = landscapes[0]
    query = (
        """
        {landscape(id: "%s") {
            id
            slug
          }
        }
        """
        % landscape.id
    )
    response = client_query(query)
    landscape_result = response.json()["data"]["landscape"]

    assert landscape_result["id"] == str(landscape.id)
    assert landscape_result["slug"] == landscape.slug


def test_landscapes_query_has_total_count(client_query, landscapes):
    response = client_query(
        """
        {landscapes {
          totalCount
          edges {
            node {
              slug
            }
          }
        }}
        """
    )
    total_count = response.json()["data"]["landscapes"]["totalCount"]

    assert total_count == len(landscapes)


def test_landscapes_query_with_json_polygon(client_query, landscapes):
    response = client_query(
        """
        {landscapes {
          edges {
            node {
              areaPolygon
            }
          }
        }}
        """
    )
    edges = response.json()["data"]["landscapes"]["edges"]
    landscapes_result = [json.loads(edge["node"]["areaPolygon"]) for edge in edges]

    for landscape in landscapes:
        assert landscape.area_polygon in landscapes_result


def test_landscapes_query_with_membership(
    client_query, managed_landscapes, landscape_user_memberships
):
    response = client_query(
        """
        {landscapes(slug: "%s") {
          edges {
            node {
              name
              membershipList {
                membershipsCount
                memberships {
                  edges {
                    node {
                      user {
                        email
                      }
                    }
                  }
                }
              }
            }
          }
        }}
        """
        % managed_landscapes[0].slug
    )

    json_response = response.json()

    membership_list = json_response["data"]["landscapes"]["edges"][0]["node"]["membershipList"]
    memberships = membership_list["memberships"]["edges"]
    assert len(memberships) == 2
    assert membership_list["membershipsCount"] == 2


def test_landscapes_query_with_membership_for_non_member(
    client_query, managed_landscapes, landscape_user_memberships
):
    response = client_query(
        """
        {landscapes(slug: "%s") {
          edges {
            node {
              name
              membershipList {
                membershipsCount
                memberships {
                  edges {
                    node {
                      user {
                        email
                      }
                    }
                  }
                }
              }
            }
          }
        }}
        """
        % managed_landscapes[1].slug
    )

    json_response = response.json()

    membership_list = json_response["data"]["landscapes"]["edges"][0]["node"]["membershipList"]
    memberships = membership_list["memberships"]["edges"]
    assert len(memberships) == 2
    assert membership_list["membershipsCount"] == 2


def test_landscapes_query_with_membership_for_anonymous_user(
    client_query_no_token, managed_landscapes, landscape_user_memberships
):
    response = client_query_no_token(
        """
        {landscapes(slug: "%s") {
          edges {
            node {
              name
              membershipList {
                membershipsCount
                memberships {
                  edges {
                    node {
                      user {
                        email
                      }
                    }
                  }
                }
              }
            }
          }
        }}
        """
        % managed_landscapes[1].slug
    )

    json_response = response.json()

    membership_list = json_response["data"]["landscapes"]["edges"][0]["node"]["membershipList"]
    memberships = membership_list["memberships"]["edges"]
    assert len(memberships) == 0
    assert membership_list["membershipsCount"] == 2


def test_landscapes_query_by_membership_email(client_query, landscape_user_memberships):
    membership = landscape_user_memberships[0]
    response = client_query(
        """
        {landscapes(membershipList_Memberships_User_Email: "%s") {
          edges {
            node {
              name
              membershipList {
                membershipsCount
                memberships {
                  edges {
                    node {
                      user {
                        email
                      }
                    }
                  }
                }
              }
            }
          }
        }}
        """
        % membership.user.email
    )

    json_response = response.json()

    membership_list = json_response["data"]["landscapes"]["edges"][0]["node"]["membershipList"]
    memberships = membership_list["memberships"]["edges"]
    assert len(memberships) == 2
    assert membership_list["membershipsCount"] == 2
