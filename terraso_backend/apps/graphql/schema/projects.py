import graphene
from django.db import transaction
from graphene import relay
from graphene_django import DjangoObjectType

from apps.soilproj.models import Project, ProjectMembership, Site

from .commons import BaseWriteMutation, TerrasoConnection
from .sites import SiteNode


class ProjectNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = Project

        filter_fields = {"name": ["icontains"]}
        fields = ("name",)

        interfaces = (relay.Node,)
        connection_class = TerrasoConnection


class ProjectAddMutation(BaseWriteMutation):
    project = graphene.Field(ProjectNode, required=True)

    model_class = Project

    class Input:
        name = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        with transaction.atomic():
            result = super().mutate_and_get_payload(root, info, **kwargs)
            ProjectMembership.objects.create(
                member=info.context.user,
                project=result.project,
                membership=ProjectMembership.MANAGER,
            )
        return result


class ProjectAddSiteMutation(relay.ClientIDMutation):
    site = graphene.Field(SiteNode, required=True)
    project = graphene.Field(ProjectNode, required=True)

    class Input:
        siteID = graphene.ID(required=True)
        projectID = graphene.ID(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, projectID, siteID):
        site = Site.objects.get(id=siteID)
        project = Project.objects.get(id=projectID)
        site.project = project
        site.save()
        return ProjectAddSiteMutation(site=site, project=project)
