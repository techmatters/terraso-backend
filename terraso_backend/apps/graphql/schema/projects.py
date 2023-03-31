import graphene
from django.db import transaction
from graphene import relay
from graphene_django import DjangoObjectType

from apps.soilproj.models import Project, ProjectMembership

from .commons import BaseWriteMutation, TerrasoConnection


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
