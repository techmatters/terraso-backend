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

import json

import pytest
from graphene_django.utils.testing import graphql_query
from mixer.backend.django import mixer

from apps.core.models.users import User
from apps.project_management.models import Project
from apps.project_management.models.sites import Site

pytestmark = pytest.mark.django_db

CREATE_PROJECT_QUERY = """
    mutation createProject($input: ProjectAddMutationInput!) {
        addProject(input: $input) {
            project {
                id
                privacy
                measurementUnits
                seen
                membershipList {
                   id
                }
            }
        }
    }
"""


def test_create_project_default_values(client, user):
    client.force_login(user)
    response = graphql_query(
        CREATE_PROJECT_QUERY,
        variables={
            "input": {
                "name": "testProject",
                "description": "A test project",
            }
        },
        client=client,
    )
    content = json.loads(response.content)
    assert "errors" not in content
    id = content["data"]["addProject"]["project"]["id"]
    project = Project.objects.get(pk=id)
    assert list([mb.user for mb in project.manager_memberships.all()]) == [user]
    assert project.measurement_units == Project.MeasurementUnit.METRIC
    assert project.privacy == Project.Privacy.PRIVATE
    assert project.description == "A test project"
    assert project.soil_settings is not None


def test_create_project_values(client, user):
    client.force_login(user)
    response = graphql_query(
        CREATE_PROJECT_QUERY,
        variables={
            "input": {
                "name": "testProject",
                "description": "A test project",
                "privacy": "PUBLIC",
                "measurementUnits": "ENGLISH",
            }
        },
        client=client,
    )
    content = json.loads(response.content)
    assert "errors" not in content
    id = content["data"]["addProject"]["project"]["id"]
    project = Project.objects.get(pk=id)
    assert list([mb.user for mb in project.manager_memberships.all()]) == [user]
    assert project.measurement_units == Project.MeasurementUnit.ENGLISH
    assert project.privacy == Project.Privacy.PUBLIC
    assert project.description == "A test project"
    assert project.soil_settings is not None


DELETE_PROJECT_GRAPHQL = """
    mutation($input: ProjectDeleteMutationInput!) {
    deleteProject(input: $input) {
        project{
        id,
        name
        }
    }
    }
"""


def test_delete_project(project_with_sites, client, project_manager, project):
    site_ids = [site.id for site in project_with_sites.site_set.all()]
    input = {"id": str(project_with_sites.id)}
    client.force_login(project_manager)
    response = graphql_query(DELETE_PROJECT_GRAPHQL, input_data=input, client=client)
    content = json.loads(response.content)
    assert "errors" not in content and "errors" not in content["data"]["deleteProject"]
    assert not Project.objects.filter(id=project_with_sites.id).exists()
    assert not Site.objects.filter(id__in=site_ids).exists()


def test_delete_project_user_not_manager(project, client, project_user):
    input = {"id": str(project.id)}
    client.force_login(project_user)
    response = graphql_query(DELETE_PROJECT_GRAPHQL, input_data=input, client=client)
    content = json.loads(response.content)
    assert "errors" in content or "errors" in content["data"]["deleteProject"]
    assert Project.objects.filter(id=project.id).exists()


@pytest.mark.parametrize("is_manager", [True, False])
def test_delete_project_transfer_sites(is_manager, project_with_sites, client, project_manager):
    other_project = mixer.blend(Project)
    if is_manager:
        other_project.add_manager(project_manager)
    else:
        other_project.add_viewer(project_manager)
    input = {"id": str(project_with_sites.id), "transferProjectId": str(other_project.id)}
    site_ids = [site.id for site in project_with_sites.site_set.all()]
    client.force_login(project_manager)
    response = graphql_query(DELETE_PROJECT_GRAPHQL, input_data=input, client=client)
    content = json.loads(response.content)
    if is_manager:
        assert "errors" not in content and "errors" not in content["data"]["deleteProject"]
        assert Site.objects.filter(project=other_project, id__in=site_ids).exists()
    else:
        assert "errors" in content or "errors" in content["data"]["deleteProject"]


ARCHIVE_PROJECT_GRAPHQL = """
    mutation($input: ProjectArchiveMutationInput!) {
    archiveProject(input: $input) {
        project{
        id,
        name
        }
    }
    }
"""


@pytest.mark.parametrize("archived", [True, False])
def test_archive_project(archived, project_with_sites, client, project_manager):
    site_ids = [site.id for site in project_with_sites.site_set.all()]
    input = {"id": str(project_with_sites.id), "archived": archived}
    client.force_login(project_manager)
    response = graphql_query(ARCHIVE_PROJECT_GRAPHQL, input_data=input, client=client)
    content = json.loads(response.content)
    assert "errors" not in content and "errors" not in content["data"]["archiveProject"]
    assert Project.objects.filter(id=project_with_sites.id, archived=archived).exists()
    assert Site.objects.filter(id__in=site_ids, archived=archived).exists()


def test_archive_project_user_not_manager(project, client, project_user):
    input = {"id": str(project.id), "archived": True}
    client.force_login(project_user)
    response = graphql_query(ARCHIVE_PROJECT_GRAPHQL, input_data=input, client=client)
    content = json.loads(response.content)
    assert "errors" in content or "errors" in content["data"]["archiveProject"]
    assert Project.objects.filter(id=project.id, archived=False).exists()


UPDATE_PROJECT_GRAPHQL = """
    mutation($input: ProjectUpdateMutationInput!) {
        updateProject(input: $input) {
            project{
                id
                name
                privacy
                measurementUnits
            }
            errors
        }
    }
"""


def test_update_project_user_is_manager(project, client, project_manager):
    input = {
        "id": str(project.id),
        "name": "test_name",
        "privacy": "PRIVATE",
        "measurementUnits": "ENGLISH",
    }
    client.force_login(project_manager)
    response = graphql_query(UPDATE_PROJECT_GRAPHQL, input_data=input, client=client)
    content = json.loads(response.content)
    assert "errors" not in content
    assert content["data"]["updateProject"]["errors"] is None
    assert content["data"]["updateProject"]["project"]["id"] == str(project.id)
    assert content["data"]["updateProject"]["project"]["name"] == "test_name"
    assert content["data"]["updateProject"]["project"]["privacy"] == "PRIVATE"
    assert content["data"]["updateProject"]["project"]["measurementUnits"] == "ENGLISH"


def test_update_project_user_not_manager(project, client, project_user):
    input = {"id": str(project.id), "name": "test_name", "privacy": "PRIVATE"}
    client.force_login(project_user)
    response = graphql_query(UPDATE_PROJECT_GRAPHQL, input_data=input, client=client)
    error_result = response.json()["data"]["updateProject"]["errors"][0]["message"]
    json_error = json.loads(error_result)
    assert json_error[0]["code"] == "change_not_allowed"


ADD_USER_GRAPHQL = """
mutation addUser($input: ProjectAddUserMutationInput!) {
  addUserToProject(input: $input) {
    project {
      id
    }
    membership {
      id
      user {
        id
      }
    }
  }
}
"""


def test_add_user_to_project(project, project_manager, client):
    user = mixer.blend(User)
    client.force_login(project_manager)
    input_data = {"projectId": str(project.id), "userId": str(user.id), "role": "VIEWER"}
    response = graphql_query(ADD_USER_GRAPHQL, input_data=input_data, client=client)
    payload = response.json()
    assert "errors" not in payload and "errors" not in payload["data"]
    data = payload["data"]["addUserToProject"]
    assert data["membership"]["user"]["id"] == str(user.id)
    project.refresh_from_db()
    assert project.viewer_memberships.filter(user=user).exists()


def test_add_user_to_project_bad_roles(project, project_manager, client):
    user = mixer.blend(User)
    client.force_login(project_manager)
    input_data = {"projectId": str(project.id), "userId": str(user.id), "role": "garbage"}
    response = graphql_query(ADD_USER_GRAPHQL, input_data=input_data, client=client)
    payload = response.json()
    assert "errors" in payload


def test_add_user_to_project_not_manager(project, project_user, client):
    user = mixer.blend(User)
    client.force_login(project_user)
    input_data = {"projectId": str(project.id), "userId": str(user.id), "role": "VIEWER"}
    response = graphql_query(ADD_USER_GRAPHQL, input_data=input_data, client=client)
    payload = response.json()
    assert "errors" in payload


def test_add_user_project_user_already_member(project, project_manager, project_user, client):
    client.force_login(project_manager)
    membership = project.get_membership(project_user)
    input_data = {
        "projectId": str(project.id),
        "userId": str(project_user.id),
        "role": membership.user_role,
    }
    response = graphql_query(ADD_USER_GRAPHQL, client=client, input_data=input_data)
    payload = response.json()
    assert "errors" not in payload
    data = payload["data"]["addUserToProject"]
    assert data["project"]["id"] == str(project.id)
    assert data["membership"]["id"] == str(membership.id)


DELETE_USER_GRAPHQL = """
mutation deleteUser($input: ProjectDeleteUserMutationInput!) {
  deleteUserFromProject(input: $input) {
    project {
      id
    }
    membership {
      user {
        id
      }
    }
  }
}
"""


def test_delete_user_from_project_manager(project, project_manager, project_user, client):
    manager_membership = project.get_membership(project_manager)
    client.force_login(project_manager)
    input_data = {"projectId": str(project.id), "userId": str(project_user.id)}
    response = graphql_query(DELETE_USER_GRAPHQL, input_data=input_data, client=client)
    payload = response.json()
    assert "errors" not in payload
    assert payload["data"]["deleteUserFromProject"]["membership"]["user"]["id"] == str(
        project_user.id
    )
    project.refresh_from_db()
    assert list(project.membership_list.memberships.all()) == [manager_membership]


def test_delete_user_from_project_delete_self(project, project_user, client):
    client.force_login(project_user)
    input_data = {"projectId": str(project.id), "userId": str(project_user.id)}
    response = graphql_query(DELETE_USER_GRAPHQL, input_data=input_data, client=client)
    payload = response.json()
    assert "errors" not in payload
    assert payload["data"]["deleteUserFromProject"]["membership"]["user"]["id"] == str(
        project_user.id
    )
    project.refresh_from_db()
    assert project_user in project.membership_list.members.all()


def test_delete_user_from_project_not_manager(project, project_user, client):
    other_user = mixer.blend(User)
    project.add_contributor(other_user)
    client.force_login(project_user)
    input_data = {"projectId": str(project.id), "userId": str(other_user.id)}
    response = graphql_query(DELETE_USER_GRAPHQL, input_data=input_data, client=client)
    payload = response.json()
    assert "errors" in payload


def test_delete_user_from_project_not_member(project, project_user, client):
    other_user = mixer.blend(User)
    client.force_login(other_user)
    input_data = {"projectId": str(project.id), "userId": str(project_user.id)}
    response = graphql_query(DELETE_USER_GRAPHQL, input_data=input_data, client=client)
    payload = response.json()
    assert "errors" in payload


def test_delete_user_from_project_last_manager(project, project_manager, client):
    client.force_login(project_manager)
    input_data = {"projectId": str(project.id), "userId": str(project_manager.id)}
    response = graphql_query(DELETE_USER_GRAPHQL, input_data=input_data, client=client)
    payload = response.json()
    assert "errors" in payload
    project.refresh_from_db()
    assert project.is_manager(project_manager) is True


def test_delete_user_from_project_other_manager(project, project_manager, user, client):
    client.force_login(project_manager)
    project.add_manager(user)
    input_data = {"projectId": str(project.id), "userId": str(user.id)}
    response = graphql_query(DELETE_USER_GRAPHQL, input_data=input_data, client=client)
    payload = response.json()
    assert "errors" not in payload
    project.refresh_from_db()
    assert project.is_manager(user) is False


UPDATE_PROJECT_ROLE_GRAPHQL = """
mutation updateProjectRole($input: ProjectUpdateUserRoleMutationInput!) {
  updateUserRoleInProject(input: $input) {
    project {
      id
    }
    membership {
      userRole
      user {
        id
      }
    }
  }
}
"""


def test_update_project_role_manager(project, project_manager, project_user, client):
    client.force_login(project_manager)
    input_data = {
        "projectId": str(project.id),
        "userId": str(project_user.id),
        "newRole": "CONTRIBUTOR",
    }
    response = graphql_query(UPDATE_PROJECT_ROLE_GRAPHQL, input_data=input_data, client=client)
    payload = response.json()
    assert "errors" not in payload
    assert payload["data"]["updateUserRoleInProject"]["membership"]["userRole"] == "CONTRIBUTOR"
    assert project.is_contributor(project_user)
    assert not project.is_viewer(project_user)
    assert response.status_code == 200


def test_update_project_role_not_manager(project, project_user, client):
    client.force_login(project_user)
    input_data = {
        "projectId": str(project.id),
        "userId": str(project_user.id),
        "newRole": "CONTRIBUTOR",
    }
    response = graphql_query(UPDATE_PROJECT_ROLE_GRAPHQL, input_data=input_data, client=client)
    payload = response.json()
    assert "errors" in payload


def test_update_project_role_user_not_in_project(project, project_user, client):
    other_user = mixer.blend(User)
    client.force_login(other_user)
    input_data = {
        "projectId": str(project.id),
        "userId": str(project_user.id),
        "newRole": "CONTRIBUTOR",
    }
    response = graphql_query(UPDATE_PROJECT_ROLE_GRAPHQL, input_data=input_data, client=client)
    payload = response.json()
    assert "errors" in payload


def test_update_project_role_target_user_not_in_project(project, project_manager, client):
    other_user = mixer.blend(User)
    client.force_login(project_manager)
    input_data = {
        "projectId": str(project.id),
        "userId": str(other_user.id),
        "newRole": "CONTRIBUTOR",
    }
    response = graphql_query(UPDATE_PROJECT_ROLE_GRAPHQL, input_data=input_data, client=client)
    payload = response.json()
    assert "errors" in payload


def test_mark_project_seen(client, user):
    client.force_login(user)
    response = graphql_query(
        CREATE_PROJECT_QUERY,
        variables={"input": {"name": "project", "privacy": "PUBLIC"}},
        client=client,
    )
    project = response.json()["data"]["addProject"]["project"]
    assert project["seen"] is True

    client.force_login(mixer.blend(User))
    response = graphql_query(
        "query project($id: ID!){ project(id: $id) { seen } }",
        variables={"id": project["id"]},
        client=client,
    )
    assert response.json()["data"]["project"]["seen"] is False

    response = graphql_query(
        """
        mutation($input: ProjectMarkSeenMutationInput!){
            markProjectSeen(input: $input) { project { seen } }
        }
        """,
        variables={"input": {"id": project["id"]}},
        client=client,
    )
    assert response.json()["data"]["markProjectSeen"]["project"]["seen"] is True
