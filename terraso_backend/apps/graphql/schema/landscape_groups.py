import graphene
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


class LandscapeGroupWriteMutation(relay.ClientIDMutation):
    landscape_group = graphene.Field(LandscapeGroupNode)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        """
        This is the method performed everytime this mutation is submitted.
        Since this is the base class for write operations, this method will be
        called both when adding and updating Landscape Groups. The `kwargs`
        receives a dictionary with all inputs informed.
        """
        _id = kwargs.pop("id", None)

        if _id:
            landscape_group = LandscapeGroup.objects.get(pk=_id)
            new_landscape = kwargs.pop("landscape_slug", None)
            new_group = kwargs.pop("group_slug", None)

            if new_landscape:
                landscape_group.landscape = Landscape.objects.get(slug=new_landscape)

            if new_group:
                landscape_group.group = Group.objects.get(slug=new_group)
        else:
            landscape_group = LandscapeGroup()
            landscape_group.is_dafault_landscape_group = False
            landscape_group.landscape = Landscape.objects.get(slug=kwargs.pop("landscape_slug"))
            landscape_group.group = Group.objects.get(slug=kwargs.pop("group_slug"))

        default_group = kwargs.pop("is_default_landscape_group", None)
        if default_group is not None:
            landscape_group.is_default_landscape_group = default_group

        try:
            landscape_group.full_clean()
        except ValidationError as exc:
            raise GraphQLValidationException.from_validation_error(exc)

        landscape_group.save()

        return cls(landscape_group=landscape_group)


class LandscapeGroupAddMutation(LandscapeGroupWriteMutation):
    class Input:
        landscape_slug = graphene.String(required=True)
        group_slug = graphene.String(required=True)
        is_default_landscape_group = graphene.Boolean(required=False, default=False)


class LandscapeGroupUpdateMutation(LandscapeGroupWriteMutation):
    class Input:
        id = graphene.ID(required=True)
        landscape_slug = graphene.String()
        group_slug = graphene.String()
        is_default_landscape_group = graphene.Boolean(required=False, default=False)


class LandscapeGroupDeleteMutation(BaseDeleteMutation):
    landscape_group = graphene.Field(LandscapeGroupNode)

    model_class = LandscapeGroup

    class Input:
        id = graphene.ID()
