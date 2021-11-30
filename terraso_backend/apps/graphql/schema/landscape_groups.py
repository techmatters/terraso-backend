from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import LandscapeGroup


class LandscapeGroupNode(DjangoObjectType):
    class Meta:
        model = LandscapeGroup
        filter_fields = ("landscape", "group", "is_default_landscape_group")
        fields = ("landscape", "group", "is_default_landscape_group")
        interfaces = (relay.Node,)
