import graphene
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import User
from apps.graphql.exceptions import GraphQLNotAllowedException

from .commons import BaseDeleteMutation, TerrasoConnection
from .constants import MutationTypes


class UserNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = User
        filter_fields = {
            "email": ["exact", "icontains"],
            "first_name": ["icontains"],
            "last_name": ["icontains"],
        }
        fields = ("email", "first_name", "last_name", "profile_image", "memberships")
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection


class UserAddMutation(relay.ClientIDMutation):
    user = graphene.Field(UserNode)

    class Input:
        first_name = graphene.String()
        last_name = graphene.String()
        email = graphene.String(required=True)
        password = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = User.objects.create_user(
            kwargs.pop("email"), password=kwargs.pop("password"), **kwargs
        )

        return cls(user=user)


class UserUpdateMutation(relay.ClientIDMutation):
    user = graphene.Field(UserNode)

    model_class = User

    class Input:
        id = graphene.ID(required=True)
        first_name = graphene.String()
        last_name = graphene.String()
        email = graphene.String()
        password = graphene.String()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        request_user = info.context.user
        _id = kwargs.pop("id")

        if str(request_user.id) != _id:
            raise GraphQLNotAllowedException(
                model_name=User.__name__, operation=MutationTypes.UPDATE
            )

        user = User.objects.get(pk=_id)
        new_password = kwargs.pop("password", None)

        if new_password:
            user.set_password(new_password)

        for attr, value in kwargs.items():
            setattr(user, attr, value)

        user.save()

        return cls(user=user)


class UserDeleteMutation(BaseDeleteMutation):
    user = graphene.Field(UserNode)
    model_class = User

    class Input:
        id = graphene.ID()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        request_user = info.context.user
        _id = kwargs.get("id")

        if str(request_user.id) != _id:
            raise GraphQLNotAllowedException(
                model_name=User.__name__, operation=MutationTypes.DELETE
            )

        return super().mutate_and_get_payload(root, info, **kwargs)
