import graphene
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField

from apps.core.models import Group

from .commons import BaseDeleteMutation, BaseWriteMutation
from .group_associations import GroupAssociationNode
from .memberships import MembershipNode


class GroupNode(DjangoObjectType):
    associations_as_parent = DjangoFilterConnectionField(GroupAssociationNode)
    associations_as_child = DjangoFilterConnectionField(GroupAssociationNode)
    memberships = DjangoFilterConnectionField(MembershipNode)

    class Meta:
        model = Group
        filter_fields = {
            "name": ["exact", "icontains", "istartswith"],
            "slug": ["icontains"],
            "description": ["icontains"],
            "associations_as_parent": ["exact"],
            "associations_as_child": ["exact"],
            "members__email": ["icontains"],
            "memberships": ["exact"],
        }
        interfaces = (relay.Node,)

    def resolve_associations_as_parent(self, info):
        return self.associations_as_parent.all()

    def resolve_associations_as_child(self, info):
        return self.associations_as_child.all()


class GroupAddMutation(BaseWriteMutation):
    group = graphene.Field(GroupNode)

    model_class = Group

    class Input:
        name = graphene.String(required=True)
        description = graphene.String()
        website = graphene.String()
        email = graphene.String()


class GroupUpdateMutation(BaseWriteMutation):
    group = graphene.Field(GroupNode)

    model_class = Group

    class Input:
        id = graphene.ID(required=True)
        name = graphene.String()
        description = graphene.String()
        website = graphene.String()
        email = graphene.String()


class GroupDeleteMutation(BaseDeleteMutation):
    group = graphene.Field(GroupNode)
    model_class = Group

    class Input:
        id = graphene.ID()
