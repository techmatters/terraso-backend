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

from apps.audit_logs.api import CHANGE, CREATE
from apps.audit_logs.models import Log
from apps.core.models import User
from apps.project_management.models import Project, Site

pytestmark = pytest.mark.django_db


CREATE_SITE_QUERY = """
    mutation createSite($input: SiteAddMutationInput!) {
        addSite(input: $input) {
           site {
              id
           }
        }
    }
"""


def site_creation_keywords():
    return {"latitude": 0, "longitude": 0, "name": "Test Site"}


def test_site_creation(client_query, user):
    kwargs = site_creation_keywords()
    response = client_query(
        CREATE_SITE_QUERY,
        variables={"input": kwargs},
    )
    content = json.loads(response.content)
    assert "errors" not in content
    id = content["data"]["addSite"]["site"]["id"]
    site = Site.objects.get(pk=id)
    assert str(site.id) == id
    assert site.latitude == pytest.approx(site.latitude)
    assert site.longitude == pytest.approx(site.longitude)
    assert site.owner == user
    assert site.created_by == user
    logs = Log.objects.all()
    assert len(logs) == 1
    log_result = logs[0]
    assert log_result.event == CREATE.value
    assert log_result.user == user
    assert log_result.resource_object == site
    expected_metadata = {'name': 'Test Site', 'latitude': 0.0, 'longitude': 0.0}
    assert log_result.metadata == expected_metadata


def test_site_creation_in_project(client, project_manager, project):
    kwargs = site_creation_keywords()
    kwargs["projectId"] = str(project.id)
    client.force_login(project_manager)
    response = graphql_query(
        CREATE_SITE_QUERY,
        variables={"input": kwargs},
        client=client,
    )
    content = json.loads(response.content)
    assert "errors" not in content and "errors" not in content["data"]
    id = content["data"]["addSite"]["site"]["id"]
    site = Site.objects.get(pk=id)
    assert site.project == project
    assert site.created_by == project_manager
    logs = Log.objects.all()
    assert len(logs) == 1
    log_result = logs[0]
    assert log_result.event == CREATE.value
    assert log_result.resource_object == site
    expected_metadata = {'name': 'Test Site', 'latitude': 0.0, 'longitude': 0.0}
    assert log_result.metadata["name"] == expected_metadata["name"]
    assert log_result.metadata["latitude"] == expected_metadata["latitude"]
    assert log_result.metadata["longitude"] == expected_metadata["longitude"]


EDIT_SITE_QUERY = """
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


def test_edit_site_in_project(client, project, project_manager, site):
    original_project = mixer.blend(Project)
    original_project.add_manager(project_manager)
    site.add_to_project(project)

    client.force_login(project_manager)
    response = graphql_query(
        EDIT_SITE_QUERY,
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

    logs = Log.objects.all()
    assert len(logs) == 1
    log_result = logs[0]
    assert log_result.event == CHANGE.value
    assert log_result.resource_object == site
    assert log_result.metadata["project_name"] == project.name


def test_adding_site_to_project_user_not_manager(client, project, site, user):
    site_creator = mixer.blend(User)
    project.add_member(user)
    client.force_login(site_creator)
    response = graphql_query(
        EDIT_SITE_QUERY,
        variables={"input": {"id": str(site.id), "projectId": str(project.id)}},
        client=client,
    )

    content = json.loads(response.content)
    assert "errors" in content


def test_adding_site_owned_by_user_to_project(client, project, site, project_manager):
    site.add_owner(project_manager)
    client.force_login(project_manager)
    response = graphql_query(
        EDIT_SITE_QUERY,
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
    assert site.owned_by(project)


@pytest.mark.parametrize("allow_adding_site", [True, False])
def test_user_can_add_site_to_project_if_project_setting_set(
    client, project, project_user, site, allow_adding_site
):
    project.settings.member_can_add_site_to_project = allow_adding_site
    project.settings.save()
    project.save()
    site.add_owner(project_user)
    client.force_login(project_user)
    response = graphql_query(
        EDIT_SITE_QUERY,
        variables={"input": {"id": str(site.id), "projectId": str(project.id)}},
        client=client,
    )
    content = json.loads(response.content)
    if allow_adding_site:
        assert "errors" not in content and "errors" not in content["data"]
        payload = content["data"]["editSite"]["site"]
        assert payload["id"] == str(site.id)
        site.refresh_from_db()
        assert site.owned_by(project)
    else:
        assert "errors" in content or "errors" in content["data"]


@pytest.mark.parametrize("allow_adding_site", [True, False])
def test_user_can_add_new_site_to_project_if_project_setting_set(
    client, project, project_user, allow_adding_site
):
    project.settings.member_can_add_site_to_project = allow_adding_site
    project.settings.save()
    project.save()
    client.force_login(project_user)
    kwargs = site_creation_keywords()
    kwargs["projectId"] = str(project.id)
    response = graphql_query(
        CREATE_SITE_QUERY,
        variables={"input": kwargs},
        client=client,
    )
    content = json.loads(response.content)
    if allow_adding_site:
        assert "errors" not in content and "errors" not in content["data"]
        payload = content["data"]["addSite"]["site"]
        site = Site.objects.get(id=payload["id"])
        assert site.owned_by(project)
    else:
        assert "errors" in content or "errors" in content["data"]
