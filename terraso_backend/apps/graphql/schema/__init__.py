import graphene
from graphene import relay
from graphene_django.filter import DjangoFilterConnectionField

from .groups import GroupNode
from .landscapes import LandscapeNode
from .users import UserNode


class Query(graphene.ObjectType):
    group = relay.Node.Field(GroupNode)
    landscape = relay.Node.Field(LandscapeNode)
    user = relay.Node.Field(UserNode)
    groups = DjangoFilterConnectionField(GroupNode)
    landscapes = DjangoFilterConnectionField(LandscapeNode)
    users = DjangoFilterConnectionField(UserNode)


schema = graphene.Schema(query=Query)
