import graphene
from graphene import relay
from graphene_django.filter import DjangoFilterConnectionField

from .groups import (
    GroupAddMutation,
    GroupDeleteMutation,
    GroupNode,
    GroupUpdateMutation,
)
from .landscapes import (
    LandscapeAddMutation,
    LandscapeDeleteMutation,
    LandscapeNode,
    LandscapeUpdateMutation,
)
from .users import UserNode


class Query(graphene.ObjectType):
    group = relay.Node.Field(GroupNode)
    landscape = relay.Node.Field(LandscapeNode)
    user = relay.Node.Field(UserNode)
    groups = DjangoFilterConnectionField(GroupNode)
    landscapes = DjangoFilterConnectionField(LandscapeNode)
    users = DjangoFilterConnectionField(UserNode)


class Mutations(graphene.ObjectType):
    add_group = GroupAddMutation.Field()
    add_landscape = LandscapeAddMutation.Field()
    update_group = GroupUpdateMutation.Field()
    update_landscape = LandscapeUpdateMutation.Field()
    delete_group = GroupDeleteMutation.Field()
    delete_landscape = LandscapeDeleteMutation.Field()


schema = graphene.Schema(query=Query, mutation=Mutations)
