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
from tests.utils import match_json

from apps.core.models import User
from apps.project_management.models.projects import Project

pytestmark = pytest.mark.django_db

PROJECT_QUERY = """
    {
      projects {
        edges {
          node {
            id
            name
            membershipList {
              id
              memberships {
                edges {
                  node {
                    id
                  }
                }
              }
            }
          }
        }
        totalCount
      }
    }
    """


def test_query_by_member(client, project, project_user):
    project2 = Project(name="2")
    project2.save()
    client.force_login(project_user)
    response = graphql_query(PROJECT_QUERY, client=client)
    assert "errors" not in response.json()
    edges = response.json()["data"]["projects"]["edges"]
    assert len(edges) == 1
    assert edges[0]["node"]["name"] == str(project.name)


def test_query_by_non_member(client, project):
    response = graphql_query(PROJECT_QUERY, client=client)
    payload = response.json()
    assert "errors" not in payload
    assert len(payload["data"]["projects"]["edges"]) == 0
    assert payload["data"]["projects"]["totalCount"] == 0


def test_query_with_deleted_member(client, project):
    user = mixer.blend(User)
    project.add_manager(user)
    project.remove_user(user)
    project.add_viewer(user)
    client.force_login(user)
    payload = graphql_query(PROJECT_QUERY, client=client).json()
    assert "errors" not in payload
    assert len(match_json("data.projects.edges[*]", payload)) == 1
