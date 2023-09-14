import json

import pytest
from graphene_django.utils.testing import graphql_query
from mixer.backend.django import mixer

from apps.audit_logs.api import CREATE
from apps.audit_logs.models import Log
from apps.core.models.users import User
from apps.project_management.models import Project
from apps.project_management.models.sites import Site

pytestmark = pytest.mark.django_db


@pytest.mark.skip("TODO: Reimplement with MembershipList")
def test_create_project(client, user):
    client.force_login(user)
    response = graphql_query(
        """
    mutation createProject($input: ProjectAddMutationInput!) {
        addProject(input: $input) {
            project {
                id
            }
        }
    }
    """,
        variables={
            "input": {"name": "testProject", "privacy": "PRIVATE", "description": "A test project"}
        },
        client=client,
    )
    content = json.loads(response.content)
    assert "errors" not in content
    id = content["data"]["addProject"]["project"]["id"]
    project = Project.objects.get(pk=id)
    assert list([mb.user for mb in project.manager_memberships.all()]) == [user]
    assert project.description == "A test project"

    logs = Log.objects.all()
    assert len(logs) == 1
    log_result = logs[0]
    assert log_result.event == CREATE.value
    assert log_result.resource_object == project
    expected_metadata = {"name": "testProject", "privacy": "private"}
    assert log_result.metadata == expected_metadata


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

pytest.mark.skip("TODO: Reimplement with MembershipList")


@pytest.mark.skip("TODO: Reimplement with MembershipList")
def test_delete_project(project_with_sites, client, project_manager):
    site_ids = [site.id for site in project_with_sites.site_set.all()]
    input = {"id": str(project_with_sites.id)}
    client.force_login(project_manager)
    response = graphql_query(DELETE_PROJECT_GRAPHQL, input_data=input, client=client)
    content = json.loads(response.content)
    assert "errors" not in content and "errors" not in content["data"]["deleteProject"]
    assert not Project.objects.filter(id=project_with_sites.id).exists()
    assert not Site.objects.filter(id__in=site_ids).exists()


@pytest.mark.skip("TODO: Reimplement with MembershipList")
def test_delete_project_user_not_manager(project, client):
    user = mixer.blend(User)
    project.add_member(user)
    input = {"id": str(project.id)}
    client.force_login(user)
    response = graphql_query(DELETE_PROJECT_GRAPHQL, input_data=input, client=client)
    content = json.loads(response.content)
    assert "errors" in content or "errors" in content["data"]["deleteProject"]
    assert Project.objects.filter(id=project.id).exists()


@pytest.mark.skip("TODO: Reimplement with MembershipList")
@pytest.mark.parametrize("is_manager", [True, False])
def test_delete_project_transfer_sites(is_manager, project_with_sites, client, project_manager):
    other_project = mixer.blend(Project)
    if is_manager:
        other_project.add_manager(project_manager)
    else:
        other_project.add_member(project_manager)
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


@pytest.mark.skip("TODO: Reimplement with MembershipList")
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


@pytest.mark.skip("TODO: Reimplement with MembershipList")
def test_archive_project_user_not_manager(project, client):
    user = mixer.blend(User)
    project.add_member(user)
    input = {"id": str(project.id), "archived": True}
    client.force_login(user)
    response = graphql_query(ARCHIVE_PROJECT_GRAPHQL, input_data=input, client=client)
    content = json.loads(response.content)
    assert "errors" in content or "errors" in content["data"]["archiveProject"]
    assert Project.objects.filter(id=project.id, archived=False).exists()


UPDATE_PROJECT_GRAPHQL = """
    mutation($input: ProjectUpdateMutationInput!) {
    updateProject(input: $input) {
        project{
        id,
        name,
        privacy
        }
        errors
    }
    }
"""


@pytest.mark.skip("TODO: Reimplement with MembershipList")
def test_update_project_user_is_manager(project, client, project_manager):
    input = {"id": str(project.id), "name": "test_name", "privacy": "PRIVATE"}
    client.force_login(project_manager)
    response = graphql_query(UPDATE_PROJECT_GRAPHQL, input_data=input, client=client)
    content = json.loads(response.content)
    assert content["data"]["updateProject"]["errors"] is None
    assert content["data"]["updateProject"]["project"]["id"] == str(project.id)
    assert content["data"]["updateProject"]["project"]["name"] == "test_name"
    assert content["data"]["updateProject"]["project"]["privacy"] == "PRIVATE"


@pytest.mark.skip("TODO: Reimplement with MembershipList")
def test_update_project_user_not_manager(project, client):
    user = mixer.blend(User)
    project.add_member(user)
    input = {"id": str(project.id), "name": "test_name", "privacy": "PRIVATE"}
    client.force_login(user)
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
    input_data = {"projectId": str(project.id), "userId": str(user.id), "role": "viewer"}
    response = graphql_query(ADD_USER_GRAPHQL, input_data=input_data, client=client)
    payload = response.json()
    assert "errors" not in payload and "errors" not in payload["data"]
    data = payload["data"]["addUserProject"]
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
    project.add_user_with_role(other_user, "contributor")
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
