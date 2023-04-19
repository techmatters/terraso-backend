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
from graphene_django.utils.testing import graphql_query
from mixer.backend.django import mixer

from apps.core.models import User
from apps.project_management.models import ProjectMembership, Site

pytestmark = pytest.mark.django_db


def test_site_creation(client_query, user):
    lat = 0
    lon = 0
    site_name = "Test Site"
    response = client_query(
        """
    mutation createSite($input: SiteAddMutationInput!) {
        addSite(input: $input) {
           site {
              id
           }
        }
    }
""",
        variables={"input": {"latitude": lat, "longitude": lon, "name": site_name}},
    )
    content = json.loads(response.content)
    assert "errors" not in content
    id = content["data"]["addSite"]["site"]["id"]
    site = Site.objects.get(pk=id)
    assert str(site.id) == id
    assert site.latitude == pytest.approx(site.latitude)
    assert site.longitude == pytest.approx(site.longitude)


ADD_CLIENT_QUERY = """
    mutation siteEditMutation($input: SiteEditMutationInput!) {
        editSite(input: $input) {
            site {
               id
               project {
                 id
               }
            }
        }
    }
"""


def test_adding_site_to_project(client, site_creator, project, site):
    ProjectMembership.objects.create(
        project=project, member=site_creator, membership=ProjectMembership.MANAGER
    )
    client.force_login(site_creator)
    response = graphql_query(
        ADD_CLIENT_QUERY,
        variables={"input": {"id": str(site.id), "projectId": str(project.id)}},
        client=client,
    )
    content = json.loads(response.content)
    assert "errors" not in content and "errors" not in content["data"]
    payload = content["data"]["editSite"]["site"]
    site_id = payload["id"]
    project_id = payload["project"]["id"]
    assert site_id == str(site.id)
    assert project_id == str(project.id)
    site.refresh_from_db()
    assert site.project.id == project.id


def test_adding_site_to_project_user_not_manager(client, project, site):
    site_creator = mixer.blend(User)
    site.creator = site_creator
    site.save()
    ProjectMembership.objects.create(
        project=project, member=site_creator, membership=ProjectMembership.MEMBER
    )
    client.force_login(site_creator)
    response = graphql_query(
        ADD_CLIENT_QUERY,
        variables={"input": {"siteID": str(site.id), "projectID": str(project.id)}},
        client=client,
    )

    content = json.loads(response.content)
    assert "errors" in content
