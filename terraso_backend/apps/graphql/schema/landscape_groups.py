import graphene
from django.conf import settings
from django.core.exceptions import ValidationError
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import Group, Landscape, LandscapeGroup
from apps.graphql.exceptions import GraphQLValidationException

from .commons import BaseDeleteMutation, TerrasoConnection


class LandscapeGroupNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = LandscapeGroup
        filter_fields = {
            "landscape": ["exact"],
            "landscape__slug": ["icontains"],
            "group": ["exact"],
            "group__slug": ["icontains"],
            "is_default_landscape_group": ["exact"],
        }
        fields = ("landscape", "group", "is_default_landscape_group")
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection


class LandscapeGroupAddMutation(relay.ClientIDMutation):
    landscape_group = graphene.Field(LandscapeGroupNode)

    class Input:
        landscape_slug = graphene.String(required=True)
        group_slug = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        """
        This is the method performed everytime this mutation is submitted.
        Since this is the base class for write operations, this method will be
        called both when adding and updating Landscape Groups. The `kwargs`
        receives a dictionary with all inputs informed.
        """
        user = info.context.user
        landscape = Landscape.objects.get(slug=kwargs.pop("landscape_slug"))
        group = Group.objects.get(slug=kwargs.pop("group_slug"))

        ff_check_permission_on = settings.FEATURE_FLAGS["CHECK_PERMISSIONS"]
        user_has_delete_permission = user.has_perm(LandscapeGroup.get_perm("add"), obj=landscape.pk)

        if ff_check_permission_on and not user_has_delete_permission:
            raise GraphQLValidationException("User has no permission to create this data.")

        landscape_group = LandscapeGroup()
        landscape_group.landscape = landscape
        landscape_group.group = group

        try:
            landscape_group.full_clean()
        except ValidationError as exc:
            raise GraphQLValidationException.from_validation_error(exc)

        landscape_group.save()

        return cls(landscape_group=landscape_group)


class LandscapeGroupDeleteMutation(BaseDeleteMutation):
    landscape_group = graphene.Field(LandscapeGroupNode)

    model_class = LandscapeGroup

    class Input:
        id = graphene.ID()
