import graphene
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import Group

from .commons import BaseDeleteMutation, BaseWriteMutation, TerrasoConnection


class GroupNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = Group
        filter_fields = {
            "name": ["exact", "icontains", "istartswith"],
            "slug": ["exact", "icontains"],
            "description": ["icontains"],
            "associations_as_parent__child_group": ["exact"],
            "associations_as_child__parent_group": ["exact"],
            "associations_as_parent__child_group__slug": ["icontains"],
            "associations_as_child__parent_group__slug": ["icontains"],
            "memberships": ["exact"],
            "associated_landscapes__is_default_landscape_group": ["exact"],
            "associated_landscapes": ["isnull"],
            "members__email": ["exact"],
        }
        fields = (
            "name",
            "slug",
            "description",
            "website",
            "email",
            "created_by",
            "memberships",
            "associations_as_parent",
            "associations_as_child",
            "associated_landscapes",
        )
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection


class GroupAddMutation(BaseWriteMutation):
    group = graphene.Field(GroupNode)

    model_class = Group

    class Input:
        name = graphene.String(required=True)
        description = graphene.String()
        website = graphene.String()
        email = graphene.String()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user

        if not cls.is_update(kwargs):
            kwargs["created_by"] = user

        return super().mutate_and_get_payload(root, info, **kwargs)


class GroupUpdateMutation(BaseWriteMutation):
    group = graphene.Field(GroupNode)

    model_class = Group

    class Input:
        id = graphene.ID(required=True)
        name = graphene.String()
        description = graphene.String()
        website = graphene.String()
        email = graphene.String()


class GroupDeleteMutation(BaseDeleteMutation):
    group = graphene.Field(GroupNode)
    model_class = Group

    class Input:
        id = graphene.ID()
