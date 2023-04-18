import json

import pytest
from graphene_django.utils.testing import graphql_query
from mixer.backend.django import mixer

from apps.core.models import User
from apps.project_management.models import Project, ProjectMembership

pytestmark = pytest.mark.django_db


def test_create_project(client_query, site_creator):
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
    assert list(project.members.all()) == [site_creator]
    membership = ProjectMembership.objects.filter(member=site_creator).first()
    assert membership.membership == ProjectMembership.MANAGER


ADD_CLIENT_QUERY = """
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
    """


def test_adding_site_to_project(client, site_creator, project, site):
    ProjectMembership.objects.create(
        project=project, member=site_creator, membership=ProjectMembership.MANAGER
    )
    client.force_login(site_creator)
    response = graphql_query(
        ADD_CLIENT_QUERY,
        variables={"input": {"siteID": str(site.id), "projectID": str(project.id)}},
        client=client,
    )
    content = json.loads(response.content)
    assert "errors" not in content and "errors" not in content["data"]
    payload = content["data"]["projectAddSiteMutation"]
    site_id = payload["site"]["id"]
    project_id = payload["project"]["id"]
    assert site_id == str(site.id)
    assert project_id == str(project.id)
    site.refresh_from_db()
    assert site.project.id == project.id


def test_adding_site_to_project_user_not_site_creator(client, project, site):
    site_creator = mixer.blend(User)
    ProjectMembership.objects.create(
        project=project, member=site_creator, membership=ProjectMembership.MANAGER
    )
    client.force_login(site_creator)
    response = graphql_query(
        ADD_CLIENT_QUERY,
        variables={"input": {"siteID": str(site.id), "projectID": str(project.id)}},
        client=client,
    )

    content = json.loads(response.content)
    assert "errors" in content["data"]


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
