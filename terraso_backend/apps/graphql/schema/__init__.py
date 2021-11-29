import graphene
from graphene import relay
from graphene_django.filter import DjangoFilterConnectionField

from .groups import (
    GroupAddMutation,
    GroupAssociationNode,
    GroupDeleteMutation,
    GroupNode,
    GroupUpdateMutation,
    MembershipNode,
)
from .landscapes import (
    LandscapeAddMutation,
    LandscapeDeleteMutation,
    LandscapeGroupNode,
    LandscapeNode,
    LandscapeUpdateMutation,
)
from .users import UserAddMutation, UserDeleteMutation, UserNode, UserUpdateMutation


class Query(graphene.ObjectType):
    group = relay.Node.Field(GroupNode)
    landscape = relay.Node.Field(LandscapeNode)
    user = relay.Node.Field(UserNode)
    landscape_group = relay.Node.Field(LandscapeGroupNode)
    membership = relay.Node.Field(MembershipNode)
    group_association = relay.Node.Field(GroupAssociationNode)
    groups = DjangoFilterConnectionField(GroupNode)
    landscapes = DjangoFilterConnectionField(LandscapeNode)
    users = DjangoFilterConnectionField(UserNode)
    landscape_groups = DjangoFilterConnectionField(LandscapeGroupNode)
    memberships = DjangoFilterConnectionField(MembershipNode)
    group_associations = DjangoFilterConnectionField(GroupAssociationNode)


class Mutations(graphene.ObjectType):
    add_group = GroupAddMutation.Field()
    add_landscape = LandscapeAddMutation.Field()
    add_user = UserAddMutation.Field()
    update_group = GroupUpdateMutation.Field()
    update_landscape = LandscapeUpdateMutation.Field()
    update_user = UserUpdateMutation.Field()
    delete_group = GroupDeleteMutation.Field()
    delete_landscape = LandscapeDeleteMutation.Field()
    delete_user = UserDeleteMutation.Field()


schema = graphene.Schema(query=Query, mutation=Mutations)
