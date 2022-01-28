import graphene
from django.conf import settings
from django.core.exceptions import ValidationError
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import Group, GroupAssociation
from apps.graphql.exceptions import (
    GraphQLNotAllowedException,
    GraphQLNotFoundException,
    GraphQLValidationException,
)

from .commons import BaseDeleteMutation, TerrasoConnection


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


class GroupAssociationAddMutation(relay.ClientIDMutation):
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

        try:
            parent_group = Group.objects.get(slug=kwargs.pop("parent_group_slug"))
        except Group.DoesNotExist:
            raise GraphQLNotFoundException(field="parent_group")

        try:
            child_group = Group.objects.get(slug=kwargs.pop("child_group_slug"))
        except Group.DoesNotExist:
            raise GraphQLNotFoundException(field="child_group")

        group_association = GroupAssociation()
        group_association.parent_group = parent_group
        group_association.child_group = child_group

        ff_check_permission_on = settings.FEATURE_FLAGS["CHECK_PERMISSIONS"]

        if ff_check_permission_on and not user.has_perm(
            GroupAssociation.get_perm("add"), obj=parent_group.pk
        ):
            raise GraphQLNotAllowedException(field="group_association", operation="add")

        try:
            group_association.full_clean()
        except ValidationError as exc:
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

        try:
            group_association = GroupAssociation.objects.get(pk=kwargs["id"])
        except GroupAssociation.DoesNotExist:
            raise GraphQLNotFoundException(field="group_association")

        ff_check_permission_on = settings.FEATURE_FLAGS["CHECK_PERMISSIONS"]

        if ff_check_permission_on and not user.has_perm(
            GroupAssociation.get_perm("delete"), obj=group_association
        ):
            raise GraphQLNotAllowedException(field="group_association", operation="delete")

        return super().mutate_and_get_payload(root, info, **kwargs)
