import pytest
from graphene_django.utils.testing import graphql_query

pytestmark = pytest.mark.django_db


@pytest.fixture
def client_query(client):
    def _client_query(*args, **kwargs):
        return graphql_query(*args, **kwargs, client=client)

    return _client_query


def test_landscapes_query(client_query, landscapes):
    response = client_query(
        """
        query {
            landscapes {
                edges {
                    node {
                        slug
                    }
                }
            }
        }
        """
    )
    edges = response.json()["data"]["landscapes"]["edges"]
    landscapes_result = [edge["node"]["slug"] for edge in edges]

    for landscape in landscapes:
        assert landscape.slug in landscapes_result


def test_landscape_groups_query(client_query, landscape_groups):
    response = client_query(
        """
        {landscapeGroups {
          edges {
            node {
              landscape {
                slug
              }
              group {
                slug
              }
              isDefaultLandscapeGroup
            }
          }
        }}
        """
    )
    edges = response.json()["data"]["landscapeGroups"]["edges"]
    nodes = [edge["node"] for edge in edges]

    landscapes_and_groups_returned = [
        (lsg["landscape"]["slug"], lsg["group"]["slug"]) for lsg in nodes
    ]

    landscapes_and_groups_expected = [
        (lsg.landscape.slug, lsg.group.slug) for lsg in landscape_groups
    ]

    assert landscapes_and_groups_expected == landscapes_and_groups_returned


def test_groups_query(client_query, groups):
    response = client_query(
        """
        query {
            groups {
                edges {
                    node {
                        slug
                    }
                }
            }
        }
        """
    )
    edges = response.json()["data"]["groups"]["edges"]
    groups_result = [edge["node"]["slug"] for edge in edges]

    for group in groups:
        assert group.slug in groups_result


def test_users_query(client_query, users):
    response = client_query(
        """
        query {
            users {
                edges {
                    node {
                        email
                    }
                }
            }
        }
        """
    )
    edges = response.json()["data"]["users"]["edges"]
    users_result = [edge["node"]["email"] for edge in edges]
    for user in users:
        assert user.email in users_result
