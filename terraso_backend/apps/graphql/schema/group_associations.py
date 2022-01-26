import graphene
from django.core.exceptions import ValidationError
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import Group, GroupAssociation
from apps.graphql.exceptions import GraphQLValidationException

from .commons import BaseDeleteMutation, TerrasoConnection


class GroupAssociationNode(DjangoObjectType):
    id = graphene.ID(source='pk', required=True)

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
        try:
            parent_group = Group.objects.get(slug=kwargs.pop("parent_group_slug"))
        except Group.DoesNotExist:
            raise GraphQLValidationException("Parent Group not found.")

        try:
            child_group = Group.objects.get(slug=kwargs.pop("child_group_slug"))
        except Group.DoesNotExist:
            raise GraphQLValidationException("Child Group not found.")

        group_association = GroupAssociation()
        group_association.parent_group = parent_group
        group_association.child_group = child_group

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
