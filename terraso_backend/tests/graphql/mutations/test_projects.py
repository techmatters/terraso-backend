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
    assert list(project.managers.all()) == [user]
    assert project.description == "A test project"

    logs = Log.objects.all()
    assert len(logs) == 1
    log_result = logs[0]
    assert log_result.event == CREATE.value
    assert log_result.resource_object == project
    expected_metadata = {"name": "testProject", "privacy": "private"}
    assert log_result.metadata == expected_metadata


def test_add_user_to_project(client, project, project_manager, user):
    client.force_login(project_manager)
    response = graphql_query(
        """
     mutation addUserToProject($input: MembershipAddMutationInput!) {
        addMembership(input: $input) {
          membership {
             id
          }
        }
     }
        """,
        variables={
            "input": {
                "userEmail": user.email,
                "groupSlug": project.group.slug,
                "userRole": "member",
            }
        },
        client=client,
    )
    content = json.loads(response.content)
    assert "errors" not in content and "errors" not in content["data"]["addMembership"]
    assert project.is_member(user)


def test_add_user_to_project_audit_log(client, project, project_manager, user):
    client.force_login(project_manager)

    assert project_manager.id != user.id

    graphql_query(
        """
     mutation addUserToProject($input: MembershipAddMutationInput!) {
        addMembership(input: $input) {
          membership {
             id
          }
        }
     }
        """,
        variables={
            "input": {
                "userEmail": user.email,
                "groupSlug": project.group.slug,
                "userRole": "member",
            }
        },
        client=client,
    )

    membership = project.group.memberships.filter(user=user).first()

    logs = Log.objects.all()
    assert len(logs) == 1
    log_result = logs[0]
    assert log_result.event == CREATE.value
    assert log_result.user_human_readable == project_manager.full_name()
    assert log_result.resource_object == membership
    expected_metadata = {
        "user_email": user.email,
        "user_role": "member",
        "project_id": str(project.id),
    }
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


def test_delete_project(project_with_sites, client, project_manager):
    site_ids = [site.id for site in project_with_sites.site_set.all()]
    input = {"id": str(project_with_sites.id)}
    client.force_login(project_manager)
    response = graphql_query(DELETE_PROJECT_GRAPHQL, input_data=input, client=client)
    content = json.loads(response.content)
    assert "errors" not in content and "errors" not in content["data"]["deleteProject"]
    assert not Project.objects.filter(id=project_with_sites.id).exists()
    assert not Site.objects.filter(id__in=site_ids).exists()


def test_delete_project_user_not_manager(project, client):
    user = mixer.blend(User)
    project.add_member(user)
    input = {"id": str(project.id)}
    client.force_login(user)
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


def test_update_project_user_is_manager(project, client, project_manager):
    input = {"id": str(project.id), "name": "test_name", "privacy": "PRIVATE"}
    client.force_login(project_manager)
    response = graphql_query(UPDATE_PROJECT_GRAPHQL, input_data=input, client=client)
    content = json.loads(response.content)
    assert content["data"]["updateProject"]["errors"] is None
    assert content["data"]["updateProject"]["project"]["id"] == str(project.id)
    assert content["data"]["updateProject"]["project"]["name"] == "test_name"
    assert content["data"]["updateProject"]["project"]["privacy"] == "PRIVATE"


def test_update_project_user_not_manager(project, client):
    user = mixer.blend(User)
    project.add_member(user)
    input = {"id": str(project.id), "name": "test_name", "privacy": "PRIVATE"}
    client.force_login(user)
    response = graphql_query(UPDATE_PROJECT_GRAPHQL, input_data=input, client=client)
    error_result = response.json()["data"]["updateProject"]["errors"][0]["message"]
    json_error = json.loads(error_result)
    assert json_error[0]["code"] == "change_not_allowed"
