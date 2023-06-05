import json

import pytest
from graphene_django.utils.testing import graphql_query
from mixer.backend.django import mixer

from apps.project_management.models import Project
from apps.core.models.users import User

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
        variables={"input": {"name": "testProject", "privacy": "PRIVATE"}},
        client=client,
    )
    content = json.loads(response.content)
    assert "errors" not in content
    id = content["data"]["addProject"]["project"]["id"]
    project = Project.objects.get(pk=id)
    assert list(project.managers.all()) == [user]


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

def test_delete_project(project, client, project_manager):
    input = {'id' : str(project.id)}
    client.force_login(project_manager)
    response = graphql_query(DELETE_PROJECT_GRAPHQL, input_data = input, client = client)
    content = json.loads(response.content)
    assert "errors" not in content and "errors" not in content["data"]["deleteProject"]
    assert not Project.objects.filter(id = project.id).exists()

def test_delete_project_user_not_manager(project, client):
    user = mixer.blend(User)
    project.add_member(user)
    input = {'id' : str(project.id)}
    client.force_login(user)
    response = graphql_query(DELETE_PROJECT_GRAPHQL, input_data = input, client = client)
    content = json.loads(response.content)
    assert ("errors" in content or "errors" in content["data"]["deleteProject"])
    assert Project.objects.filter(id = project.id).exists()