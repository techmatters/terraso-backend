import graphene
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import Landscape

from .commons import BaseDeleteMutation, BaseWriteMutation


class LandscapeNode(DjangoObjectType):
    class Meta:
        model = Landscape
        filter_fields = ["name", "description", "groups"]
        interfaces = (relay.Node,)


class LandscapeAddMutation(BaseWriteMutation):
    landscape = graphene.Field(LandscapeNode)

    model_class = Landscape

    class Input:
        name = graphene.String(required=True)
        description = graphene.String()
        website = graphene.String()
        location = graphene.String()


class LandscapeUpdateMutation(BaseWriteMutation):
    landscape = graphene.Field(LandscapeNode)

    model_class = Landscape

    class Input:
        id = graphene.ID(required=True)
        name = graphene.String()
        description = graphene.String()
        website = graphene.String()
        location = graphene.String()


class LandscapeDeleteMutation(BaseDeleteMutation):
    landscape = graphene.Field(LandscapeNode)

    model_class = Landscape

    class Input:
        id = graphene.ID()
