import pytest
from graphene_django.utils.testing import graphql_query

from apps.project_management.models import Site

pytestmark = pytest.mark.django_db


def test_query_by_project(client_query, project, project_manager, site):
    site.project = project
    site.owner = None
    site.save()
    site2 = Site(name=2, project=project, latitude=site.latitude, longitude=site.longitude)
    site2.save()
    query = """
    {
      sites(orderBy: "%s", project_Id: "%s") {
        edges {
          node {
            id
            name
          }
        }
      }
    }
    """ % (
        "created_at",
        project.id,
    )
    response = graphql_query(
        query,
    )
    assert "errors" not in response.json()
    edges = response.json()["data"]["sites"]["edges"]
    assert len(edges) == 2
    assert edges[1]["node"]["name"] == str(site2.name)

    query = """
        {
          sites(orderBy: "-%s", project_Id: "%s") {
            edges {
              node {
                id
                name
              }
            }
          }
        }
        """ % (
        "created_at",
        project.id,
    )
    response = graphql_query(
        query,
    )
    assert "errors" not in response.json()
    edges = response.json()["data"]["sites"]["edges"]
    assert len(edges) == 2
    assert edges[0]["node"]["name"] == str(site2.name)
