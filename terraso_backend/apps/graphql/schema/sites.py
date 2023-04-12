import graphene
from graphene import relay
from graphene_django import DjangoObjectType

from apps.soilproj.models import Site

from .commons import BaseWriteMutation, TerrasoConnection


class SiteNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = Site

        filter_fields = {"name": ["icontains"]}
        fields = ("name", "latitude", "longitude")

        interfaces = (relay.Node,)
        connection_class = TerrasoConnection


class SiteAddMutation(BaseWriteMutation):
    site = graphene.Field(SiteNode, required=True)

    model_class = Site

    class Input:
        name = graphene.String(required=True)
        latitude = graphene.Float(required=True)
        longitude = graphene.Float(required=True)
