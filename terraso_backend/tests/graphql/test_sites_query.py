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
from graphene_django.utils.testing import graphql_query
from mixer.backend.django import mixer

from apps.core.models.users import User
from apps.project_management.models import Site
from apps.project_management.models.projects import Project

pytestmark = pytest.mark.django_db


def test_query_site_fields(client, project, project_user):
    sites = [
        Site(
            name="site 1",
            latitude=1.0,
            longitude=-1.0,
            elevation=1.0,
            owner=project_user,
            privacy="PRIVATE",
            archived=False,
        ),
        Site(
            name="site 2",
            latitude=-2.0,
            longitude=2.0,
            elevation=2.0,
            project=project,
            privacy="PUBLIC",
            archived=True,
        ),
    ]
    for site in sites:
        site.save()

    query = """
    {
      site(id: "%s") {
        id
        name
        latitude
        longitude
        elevation
        privacy
        archived
        owner { id }
        project { id }
      }
    }
    """
    client.force_login(project_user)

    for site, response in [(site, graphql_query(query % site.id, client=client)) for site in sites]:
        assert "errors" not in response.json()
        site_json = response.json()["data"]["site"]
        assert site_json["name"] == site.name
        assert site_json["latitude"] == site.latitude
        assert site_json["longitude"] == site.longitude
        assert site_json["elevation"] == site.elevation
        assert site_json["privacy"] == site.privacy
        assert site_json["archived"] == site.archived
        if site_json["owner"] is None:
            assert site.owner is None
        else:
            assert site.owner is not None and site_json["owner"]["id"] == str(site.owner.id)
        if site_json["project"] is None:
            assert site.project is None
        else:
            assert site.project is not None and site_json["project"]["id"] == str(site.project.id)


def test_query_by_project(client, project, project_manager, site):
    site.project = project
    site.owner = None
    site.save()
    site2 = Site(
        name=2,
        project=project,
        latitude=site.latitude,
        longitude=site.longitude,
        elevation=site.elevation,
    )
    site2.save()
    query = """
    {
      sites(orderBy: "%s", project: "%s") {
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
    client.force_login(project_manager)
    response = graphql_query(query, client=client)
    assert "errors" not in response.json()
    edges = response.json()["data"]["sites"]["edges"]
    assert len(edges) == 2
    assert edges[1]["node"]["name"] == str(site2.name)

    query = """
        {
          sites(orderBy: "-%s", project: "%s") {
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
    response = graphql_query(query, client=client)
    assert "errors" not in response.json()
    edges = response.json()["data"]["sites"]["edges"]
    assert len(edges) == 2
    assert edges[0]["node"]["name"] == str(site2.name)


def test_query_by_project_member(client, project, site, project_user):
    project2 = Project(name="2")
    project2.save()
    site.project = project
    site.owner = None
    site.save()
    site2 = Site(
        name="2",
        project=project2,
        latitude=site.latitude,
        longitude=site.longitude,
        elevation=site.elevation,
    )
    site2.save()
    site3 = Site(
        name="3",
        owner=project_user,
        latitude=site.latitude,
        longitude=site.longitude,
        elevation=site.elevation,
    )
    site3.save()
    query = """
    {
      sites(project_Member: "%s") {
        edges {
          node {
            id
            name
          }
        }
      }
    }
    """ % (
        project_user.id,
    )
    client.force_login(project_user)
    response = graphql_query(query, client=client)
    assert "errors" not in response.json()
    edges = response.json()["data"]["sites"]["edges"]
    assert len(edges) == 1
    assert edges[0]["node"]["name"] == str(site.name)


def test_query_by_owner(client, project, site, user):
    user2 = mixer.blend(User)
    site2 = Site(
        name="2",
        owner=user2,
        latitude=site.latitude,
        longitude=site.longitude,
        elevation=site.elevation,
    )
    site2.save()
    query = """
    {
      sites(owner: "%s") {
        edges {
          node {
            id
            name
          }
        }
      }
    }
    """ % (
        user2.id,
    )
    client.force_login(user2)
    response = graphql_query(query, client=client)
    assert "errors" not in response.json()
    edges = response.json()["data"]["sites"]["edges"]
    assert len(edges) == 1
    assert edges[0]["node"]["name"] == str(site2.name)


def test_query_site_permissions(client, client_query, project, project_manager, site, user):
    site.project = None
    site.owner = project_manager
    site.save()
    client.force_login(project_manager)
    assert project_manager != user
    site2 = Site(
        name=2,
        latitude=site.latitude,
        longitude=site.longitude,
        elevation=site.elevation,
        owner=user,
    )
    site2.save()
    site3 = Site(
        name=3,
        latitude=site.latitude,
        longitude=site.longitude,
        elevation=site.elevation,
        owner=user,
    )
    site3.save()
    query = """
       {
         sites(orderBy: "%s") {
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
    )
    response = graphql_query(query, client=client)

    assert "errors" not in response.json()
    edges = response.json()["data"]["sites"]["edges"]
    assert len(edges) == 1

    site.project = project
    site.owner = None
    site.save()
    client.force_login(project_manager)
    query = """
       {
         sites(orderBy: "%s") {
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
    )
    response = graphql_query(query, client=client)
    assert "errors" not in response.json()
    edges = response.json()["data"]["sites"]["edges"]
    assert len(edges) == 1

    client.force_login(user)
    query = """
           {
             sites(orderBy: "%s") {
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
    )
    response = graphql_query(query, client=client)
    assert "errors" not in response.json()
    edges = response.json()["data"]["sites"]["edges"]
    assert len(edges) == 2


def test_archived_site_not_displayed(archived_site, user, client):
    client.force_login(user)
    response = graphql_query(
        """
      query getSites($archived: Boolean) {
        sites(archived: $archived) {
          edges {
            node {
              id
              name
            }
          }
        }
      }
    """,
        client=client,
        variables={"archived": False},
    )
    assert "errors" not in response.json()
    edges = response.json()["data"]["sites"]["edges"]
    assert len(edges) == 0
