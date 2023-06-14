import json

import pytest
from graphene_django.utils.testing import graphql_query

from apps.audit_logs.api import CREATE
from apps.audit_logs.models import Log
from apps.project_management.models import Project

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

    logs = Log.objects.all()
    assert len(logs) == 1
    log_result = logs[0]
    assert log_result.event == CREATE.value
    assert log_result.resource_object == project
    expected_metadata = {'name': 'testProject', 'privacy': 'private'}
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
