import graphene
from graphene import relay
from graphene_django.filter import DjangoFilterConnectionField

from .group_associations import (
    GroupAssociationAddMutation,
    GroupAssociationDeleteMutation,
    GroupAssociationNode,
)
from .groups import (
    GroupAddMutation,
    GroupDeleteMutation,
    GroupNode,
    GroupUpdateMutation,
)
from .landscape_groups import (
    LandscapeGroupAddMutation,
    LandscapeGroupDeleteMutation,
    LandscapeGroupNode,
    LandscapeGroupUpdateMutation,
)
from .landscapes import (
    LandscapeAddMutation,
    LandscapeDeleteMutation,
    LandscapeNode,
    LandscapeUpdateMutation,
)
from .memberships import (
    MembershipAddMutation,
    MembershipDeleteMutation,
    MembershipNode,
    MembershipUpdateMutation,
)
from .users import UserAddMutation, UserDeleteMutation, UserNode, UserUpdateMutation


class Query(graphene.ObjectType):
    group = relay.Node.Field(GroupNode)
    landscape = relay.Node.Field(LandscapeNode)
    landscape_group = relay.Node.Field(LandscapeNode)
    user = relay.Node.Field(UserNode)
    landscape_group = relay.Node.Field(LandscapeGroupNode)
    membership = relay.Node.Field(MembershipNode)
    group_association = relay.Node.Field(GroupAssociationNode)
    groups = DjangoFilterConnectionField(GroupNode)
    landscapes = DjangoFilterConnectionField(LandscapeNode)
    landscape_groups = DjangoFilterConnectionField(LandscapeGroupNode)
    users = DjangoFilterConnectionField(UserNode)
    landscape_groups = DjangoFilterConnectionField(LandscapeGroupNode)
    memberships = DjangoFilterConnectionField(MembershipNode)
    group_associations = DjangoFilterConnectionField(GroupAssociationNode)


class Mutations(graphene.ObjectType):
    add_group = GroupAddMutation.Field()
    add_landscape = LandscapeAddMutation.Field()
    add_user = UserAddMutation.Field()
    add_landscape_group = LandscapeGroupAddMutation.Field()
    add_group_association = GroupAssociationAddMutation.Field()
    add_membership = MembershipAddMutation.Field()
    update_group = GroupUpdateMutation.Field()
    update_landscape = LandscapeUpdateMutation.Field()
    update_landscape_group = LandscapeGroupUpdateMutation.Field()
    update_membership = MembershipUpdateMutation.Field()
    update_user = UserUpdateMutation.Field()
    delete_group = GroupDeleteMutation.Field()
    delete_landscape = LandscapeDeleteMutation.Field()
    delete_user = UserDeleteMutation.Field()
    delete_landscape_group = LandscapeGroupDeleteMutation.Field()
    delete_group_association = GroupAssociationDeleteMutation.Field()
    delete_membership = MembershipDeleteMutation.Field()


schema = graphene.Schema(query=Query, mutation=Mutations)
