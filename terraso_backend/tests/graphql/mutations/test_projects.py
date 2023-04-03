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


def test_adding_site_to_project(client_query, user, project, site):
    response = client_query(
        """
    mutation addSiteToProject($input: ProjectAddSiteMutationInput!) {
        projectAddSiteMutation(input: $input) {
            site {
               id
            }
            project {
               id
            }
        }
    }
    """,
        variables={"input": {"siteID": str(site.id), "projectID": str(project.id)}},
    )
    content = json.loads(response.content)
    assert "errors" not in content
    payload = content["data"]["projectAddSiteMutation"]
    site_id = payload["site"]["id"]
    project_id = payload["project"]["id"]
    assert site_id == str(site.id)
    assert project_id == str(project.id)
    site.refresh_from_db()
    assert site.project.id == project.id
