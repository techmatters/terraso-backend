from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import Landscape


class LandscapeNode(DjangoObjectType):
    class Meta:
        model = Landscape
        filter_fields = ["name", "description", "groups"]
        interfaces = (relay.Node,)
