import json

import pytest

from apps.soilproj.models import Project, ProjectMembership

pytestmark = pytest.mark.django_db


def test_create_project(client_query, user):
    response = client_query(
        """
    mutation createProject($input: ProjectAddMutationInput!) {
        projectAddMutation(input: $input) {
            project {
                id
            }
        }
    }
    """,
        variables={"input": {"name": "testProject"}},
    )
    content = json.loads(response.content)
    assert "errors" not in content
    id = content["data"]["projectAddMutation"]["project"]["id"]
    project = Project.objects.get(pk=id)
    assert list(project.members.all()) == [user]
    membership = ProjectMembership.objects.filter(member=user).first()
    assert membership.membership == ProjectMembership.MANAGER
