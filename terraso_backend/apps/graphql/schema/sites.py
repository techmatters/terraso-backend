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
        fields = ("name", "lat_deg", "lon_deg")

        interfaces = (relay.Node,)
        connection_class = TerrasoConnection


class SiteAddMutation(BaseWriteMutation):
    site = graphene.Field(SiteNode, required=True)

    model_class = Site

    class Input:
        name = graphene.String(required=True)
        lat_deg = graphene.Float(required=True)
        lon_deg = graphene.Float(required=True)
