import graphene
import structlog
from django.core.exceptions import ValidationError
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import Group, GroupAssociation
from apps.graphql.exceptions import (
    GraphQLNotAllowedException,
    GraphQLNotFoundException,
    GraphQLValidationException,
)

from .commons import BaseDeleteMutation, BaseMutation, TerrasoConnection
from .constants import MutationTypes

logger = structlog.get_logger(__name__)


class GroupAssociationNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = GroupAssociation
        filter_fields = {
            "parent_group": ["exact"],
            "child_group": ["exact"],
            "parent_group__slug": ["icontains"],
            "child_group__slug": ["icontains"],
        }
        fields = ("parent_group", "child_group")
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection


class GroupAssociationAddMutation(BaseMutation):
    group_association = graphene.Field(GroupAssociationNode)

    class Input:
        parent_group_slug = graphene.String(required=True)
        child_group_slug = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        """
        This is the method performed everytime this mutation is submitted.
        This method will be called when adding Group Associations. The `kwargs`
        receives a dictionary with all inputs informed.
        """
        user = info.context.user

        parent_group_slug = kwargs.pop("parent_group_slug")
        child_group_slug = kwargs.pop("child_group_slug")

        try:
            parent_group = Group.objects.get(slug=parent_group_slug)
        except Group.DoesNotExist:
            logger.error(
                "Parent group not found when adding Group Association",
                extra={"parent_group_slug": parent_group_slug},
            )
            raise GraphQLNotFoundException(
                field="parent_group", model_name=GroupAssociation.__name__
            )

        try:
            child_group = Group.objects.get(slug=child_group_slug)
        except Group.DoesNotExist:
            logger.error(
                "Child group not found when adding Group Association",
                extra={"child_group_slug": child_group_slug},
            )
            raise GraphQLNotFoundException(
                field="child_group", model_name=GroupAssociation.__name__
            )

        group_association = GroupAssociation()
        group_association.parent_group = parent_group
        group_association.child_group = child_group

        if not user.has_perm(GroupAssociation.get_perm("add"), obj=parent_group.pk):
            logger.info(
                "Attempt to create a Group Association, but user has no permission",
                extra={"user_id": user.pk},
            )
            raise GraphQLNotAllowedException(
                model_name=GroupAssociation.__name__, operation=MutationTypes.CREATE
            )

        try:
            # Do not call full_clean(), as it calls validate_constraints(). Validating uniqueness
            # in Python (instead of in the database) provides less information -- no row ID
            # for the violation is included.
            group_association.clean_fields()
            group_association.clean()
            group_association.validate_unique()

        except ValidationError as exc:
            logger.error(
                "Attempt to create a Group Association, but model is invalid",
                extra={"validation_error": exc},
            )
            raise GraphQLValidationException.from_validation_error(exc)

        group_association.save()

        return cls(group_association=group_association)


class GroupAssociationDeleteMutation(BaseDeleteMutation):
    group_association = graphene.Field(GroupAssociationNode)

    model_class = GroupAssociation

    class Input:
        id = graphene.ID()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user

        group_association_id = kwargs["id"]

        try:
            group_association = GroupAssociation.objects.get(pk=group_association_id)
        except GroupAssociation.DoesNotExist:
            logger.error(
                "Attempt to delete a Group Association, but it as not found",
                extra={"group_association_id": group_association_id},
            )
            raise GraphQLNotFoundException(model_name=GroupAssociation.__name__)

        if not user.has_perm(GroupAssociation.get_perm("delete"), obj=group_association):
            logger.info(
                "Attempt to delete a Group Association, but user has no permission",
                extra={"user_id": user.pk, "group_association": group_association_id},
            )
            raise GraphQLNotAllowedException(
                model_name=GroupAssociation.__name__, operation=MutationTypes.DELETE
            )
        return super().mutate_and_get_payload(root, info, **kwargs)
