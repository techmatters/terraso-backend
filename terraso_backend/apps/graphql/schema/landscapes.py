import graphene
from django.conf import settings
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import Landscape
from apps.graphql.exceptions import GraphQLValidationException

from .commons import BaseDeleteMutation, BaseWriteMutation, TerrasoConnection


class LandscapeNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = Landscape
        filter_fields = {
            "name": ["icontains"],
            "description": ["icontains"],
            "slug": ["exact", "icontains"],
            "website": ["icontains"],
            "location": ["icontains"],
        }
        fields = (
            "name",
            "slug",
            "description",
            "website",
            "location",
            "created_by",
            "associated_groups",
        )
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection


class LandscapeAddMutation(BaseWriteMutation):
    landscape = graphene.Field(LandscapeNode)

    model_class = Landscape

    class Input:
        name = graphene.String(required=True)
        description = graphene.String()
        website = graphene.String()
        location = graphene.String()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user

        if not cls.is_update(kwargs):
            kwargs["created_by"] = user

        return super().mutate_and_get_payload(root, info, **kwargs)


class LandscapeUpdateMutation(BaseWriteMutation):
    landscape = graphene.Field(LandscapeNode)

    model_class = Landscape

    class Input:
        id = graphene.ID(required=True)
        name = graphene.String()
        description = graphene.String()
        website = graphene.String()
        location = graphene.String()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user

        if not settings.FEATURE_FLAGS["CHECK_PERMISSIONS"]:
            return super().mutate_and_get_payload(root, info, **kwargs)

        if not user.has_perm(Landscape.get_perm("change"), obj=kwargs["id"]):
            raise GraphQLValidationException("User has no permission to change the Landscape.")

        return super().mutate_and_get_payload(root, info, **kwargs)


class LandscapeDeleteMutation(BaseDeleteMutation):
    landscape = graphene.Field(LandscapeNode)

    model_class = Landscape

    class Input:
        id = graphene.ID()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user

        ff_check_permission_on = settings.FEATURE_FLAGS["CHECK_PERMISSIONS"]
        user_has_delete_permission = user.has_perm(Landscape.get_perm("delete"), obj=kwargs["id"])

        if ff_check_permission_on and not user_has_delete_permission:
            raise GraphQLValidationException("User has no permission to delete this data.")

        return super().mutate_and_get_payload(root, info, **kwargs)
