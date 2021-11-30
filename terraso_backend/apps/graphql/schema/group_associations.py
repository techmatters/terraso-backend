from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import GroupAssociation


class GroupAssociationNode(DjangoObjectType):
    class Meta:
        model = GroupAssociation
        filter_fields = ("parent_group", "child_group")
        fields = ("parent_group", "child_group")
        interfaces = (relay.Node,)
