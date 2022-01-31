import django_filters
import graphene
from django.conf import settings
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import Group
from apps.graphql.exceptions import GraphQLNotAllowedException

from .commons import BaseDeleteMutation, BaseWriteMutation, TerrasoConnection
from .constants import MutationTypes


class GroupFilterSet(django_filters.FilterSet):
    # TODO: members__email was kept for backward compatibility. Remove as soon
    # as the web client be updated to use memberships__email filter
    members__email = django_filters.CharFilter(method="filter_memberships_email")
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

        if not settings.FEATURE_FLAGS["CHECK_PERMISSIONS"]:
            return super().mutate_and_get_payload(root, info, **kwargs)

        if not user.has_perm(Group.get_perm("change"), obj=kwargs["id"]):
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

        ff_check_permission_on = settings.FEATURE_FLAGS["CHECK_PERMISSIONS"]
        user_has_delete_permission = user.has_perm(Group.get_perm("delete"), obj=kwargs["id"])

        if ff_check_permission_on and not user_has_delete_permission:
            raise GraphQLNotAllowedException(
                model_name=Group.__name__, operation=MutationTypes.DELETE
            )

        return super().mutate_and_get_payload(root, info, **kwargs)
