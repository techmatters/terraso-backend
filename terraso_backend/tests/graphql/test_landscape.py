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
