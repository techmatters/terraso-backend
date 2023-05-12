import graphene
from graphene_django.filter import DjangoFilterConnectionField

from .test_users import GenerateTestUserTokenMutation, TestUserNode


class Mutations(graphene.ObjectType):
    generate_test_user_token = GenerateTestUserTokenMutation.Field()


class Query(graphene.ObjectType):
    test_users = DjangoFilterConnectionField(TestUserNode)


admin_schema = graphene.Schema(mutation=Mutations, query=Query)
