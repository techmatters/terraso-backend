import graphene
import structlog
from django.core.exceptions import ValidationError
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import Group, Landscape, LandscapeGroup
from apps.graphql.exceptions import (
    GraphQLNotAllowedException,
    GraphQLNotFoundException,
    GraphQLValidationException,
)

from .commons import BaseDeleteMutation, TerrasoConnection
from .constants import MutationTypes

logger = structlog.get_logger(__name__)


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
        fields = (
            "landscape",
            "group",
            "is_default_landscape_group",
            "is_partnership",
            "partnership_year",
        )
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
        landscape_slug = kwargs.pop("landscape_slug")
        group_slug = kwargs.pop("group_slug")

        try:
            landscape = Landscape.objects.get(slug=landscape_slug)
        except Landscape.DoesNotExist:
            logger.error(
                "Landscape not found when adding Landscape Group",
                extra={"landscape_slug": landscape_slug},
            )
            raise GraphQLNotFoundException(field="landscape", model_name=LandscapeGroup.__name__)

        try:
            group = Group.objects.get(slug=group_slug)
        except Group.DoesNotExist:
            logger.error(
                "Group not found when adding Landscape Group", extra={"group_slug": group_slug}
            )
            raise GraphQLNotFoundException(field="group", model_name=LandscapeGroup.__name__)

        if not user.has_perm(LandscapeGroup.get_perm("add"), obj=landscape.pk):
            logger.info(
                "Attempt to add a Landscape Group, but user has no permission",
                extra={
                    "user_id": user.pk,
                    "landscape_slug": landscape_slug,
                    "group_slug": group_slug,
                },
            )
            raise GraphQLNotAllowedException(
                model_name=LandscapeGroup.__name__, operation=MutationTypes.CREATE
            )

        landscape_group = LandscapeGroup()
        landscape_group.landscape = landscape
        landscape_group.group = group

        try:
            # Do not call full_clean(), as it calls validate_constraints(). Validating uniqueness
            # in Python (instead of in the database) provides less information -- no row ID
            # for the violation is included.
            landscape_group.clean_fields()
            landscape_group.clean()
            landscape_group.validate_unique()

        except ValidationError as exc:
            logger.error(
                "Attempt to create a Landscape Group, but model is invalid",
                extra={"validation_error": exc},
            )
            raise GraphQLValidationException.from_validation_error(exc)

        landscape_group.save()

        return cls(landscape_group=landscape_group)


class LandscapeGroupDeleteMutation(BaseDeleteMutation):
    landscape_group = graphene.Field(LandscapeGroupNode)

    model_class = LandscapeGroup

    class Input:
        id = graphene.ID()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        landscape_group_id = kwargs["id"]

        try:
            landscape_group = LandscapeGroup.objects.get(pk=landscape_group_id)
        except LandscapeGroup.DoesNotExist:
            logger.error(
                "Attempt to delete a Landscape Group, but it as not found",
                extra={"landscape_group_id": landscape_group_id},
            )
            raise GraphQLNotFoundException(model_name=LandscapeGroup.__name__)

        if not user.has_perm(LandscapeGroup.get_perm("delete"), obj=landscape_group):
            logger.info(
                "Attempt to delete a Landscape Group, but user has no permission",
                extra={"user_id": user.pk, "landscape_group_id": landscape_group_id},
            )
            raise GraphQLNotAllowedException(
                model_name=LandscapeGroup.__name__, operation=MutationTypes.DELETE
            )

        return super().mutate_and_get_payload(root, info, **kwargs)
