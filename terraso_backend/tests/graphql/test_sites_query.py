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


def test_query_by_project(client, project, project_manager, site):
    site.project = project
    site.owner = None
    site.save()
    site2 = Site(name=2, project=project, latitude=site.latitude, longitude=site.longitude)
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
    project2.group = project2.create_default_group("2")
    project2.settings = project2.default_settings()
    project2.save()
    site.project = project
    site.owner = None
    site.save()
    site2 = Site(name="2", project=project2, latitude=site.latitude, longitude=site.longitude)
    site2.save()
    site3 = Site(name="3", owner=project_user, latitude=site.latitude, longitude=site.longitude)
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
    site2 = Site(name="2", owner=user2, latitude=site.latitude, longitude=site.longitude)
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
    project.add_manager(project_manager)
    site.project = None
    site.owner = project_manager
    site.save()
    client.force_login(project_manager)
    assert project_manager != user
    site2 = Site(name=2, latitude=site.latitude, longitude=site.longitude, owner=user)
    site2.save()
    site3 = Site(name=3, latitude=site.latitude, longitude=site.longitude, owner=user)
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
