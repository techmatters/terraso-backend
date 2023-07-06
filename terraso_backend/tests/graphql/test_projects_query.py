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

from apps.project_management.models.projects import Project

pytestmark = pytest.mark.django_db


def test_query_by_member(client, project, project_user):
    project2 = Project(name="2")
    project2.group = project2.create_default_group("2")
    project2.settings = project2.default_settings()
    project2.save()
    query = """
    {
      projects(member: "%s") {
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
    edges = response.json()["data"]["projects"]["edges"]
    assert len(edges) == 1
    assert edges[0]["node"]["name"] == str(project.name)
