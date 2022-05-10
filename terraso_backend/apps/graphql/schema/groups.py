import django_filters
import graphene
import structlog
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import Group
from apps.graphql.exceptions import GraphQLNotAllowedException

from .commons import BaseDeleteMutation, BaseWriteMutation, TerrasoConnection
from .constants import MutationTypes

logger = structlog.get_logger(__name__)


class GroupFilterSet(django_filters.FilterSet):
    memberships__email = django_filters.CharFilter(method="filter_memberships_email")
    associated_landscapes__is_default_landscape_group = django_filters.BooleanFilter(
        method="filter_associated_landscapes"
    )
    associated_landscapes__isnull = django_filters.BooleanFilter(
        method="filter_associated_landscapes"
    )

    class Meta:
        model = Group
        fields = {
            "name": ["exact", "icontains", "istartswith"],
            "slug": ["exact", "icontains"],
            "description": ["icontains"],
        }

    def filter_memberships_email(self, queryset, name, value):
        return queryset.filter(memberships__user__email=value, memberships__deleted_at__isnull=True)

    def filter_associated_landscapes(self, queryset, name, value):
        filters = {"associated_landscapes__deleted_at__isnull": True}
        filters[name] = value
        return queryset.filter(**filters)


class GroupNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = Group
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
            "data_entries",
        )
        filterset_class = GroupFilterSet
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

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        group_id = kwargs["id"]

        if not user.has_perm(Group.get_perm("change"), obj=group_id):
            logger.info(
                "Attempt to update a Group, but user has no permission",
                extra={"user_id": user.pk, "group_id": group_id},
            )
            raise GraphQLNotAllowedException(
                model_name=Group.__name__, operation=MutationTypes.UPDATE
            )

        return super().mutate_and_get_payload(root, info, **kwargs)


class GroupDeleteMutation(BaseDeleteMutation):
    group = graphene.Field(GroupNode)
    model_class = Group

    class Input:
        id = graphene.ID()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        group_id = kwargs["id"]

        if not user.has_perm(Group.get_perm("delete"), obj=group_id):
            logger.info(
                "Attempt to delete a Group, but user has no permission",
                extra={"user_id": user.pk, "group_id": group_id},
            )
            raise GraphQLNotAllowedException(
                model_name=Group.__name__, operation=MutationTypes.DELETE
            )

        return super().mutate_and_get_payload(root, info, **kwargs)
