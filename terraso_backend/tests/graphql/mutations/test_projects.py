import json

import pytest

from apps.project_management.models import Project, ProjectMembership

pytestmark = pytest.mark.django_db


def test_create_project(client_query, site_creator):
    response = client_query(
        """
    mutation createProject($input: ProjectAddMutationInput!) {
        addProject(input: $input) {
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
    id = content["data"]["addProject"]["project"]["id"]
    project = Project.objects.get(pk=id)
    assert list(project.members.all()) == [site_creator]
    membership = ProjectMembership.objects.filter(member=site_creator).first()
    assert membership.membership == ProjectMembership.MANAGER
