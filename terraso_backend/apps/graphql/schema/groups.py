# Copyright © 2021-2023 Technology Matters
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see https://www.gnu.org/licenses/.

import django_filters
import graphene
import structlog
from django.db import transaction
from graphene import relay
from graphene_django import DjangoObjectType

from apps.collaboration.models import MembershipList
from apps.core.models import Group
from apps.graphql.exceptions import GraphQLNotAllowedException

from .commons import BaseDeleteMutation, BaseWriteMutation, TerrasoConnection
from .constants import MutationTypes
from .shared_resources_mixin import SharedResourcesMixin

logger = structlog.get_logger(__name__)


class GroupFilterSet(django_filters.FilterSet):
    memberships__email = django_filters.CharFilter(method="filter_memberships_email")
    associated_landscapes__isnull = django_filters.BooleanFilter(
        method="filter_associated_landscapes"
    )
    associated_landscapes__is_partnership = django_filters.BooleanFilter(
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
        return queryset.filter(
            membership_list__memberships__user__email=value,
            membership_list__memberships__deleted_at__isnull=True,
        )

    def filter_associated_landscapes(self, queryset, name, value):
        filters = {"associated_landscapes__deleted_at__isnull": True}
        filters[name] = value
        # TODO Removed duplicated group results using order_by('slug').distinct('slug')
        # Is there a better way to do this?
        return queryset.filter(**filters).order_by("slug").distinct("slug")


class GroupNode(DjangoObjectType, SharedResourcesMixin):
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
            "membership_list",
            "associations_as_parent",
            "associations_as_child",
            "associated_landscapes",
        )
        filterset_class = GroupFilterSet
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection

    @classmethod
    def get_queryset(cls, queryset, info):
        return queryset.exclude(
            associated_landscapes__is_default_landscape_group=True,
        )


class GroupAddMutation(BaseWriteMutation):
    group = graphene.Field(GroupNode)

    model_class = Group

    class Input:
        name = graphene.String(required=True)
        description = graphene.String()
        website = graphene.String()
        email = graphene.String()
        membership_type = graphene.String()

    @classmethod
    @transaction.atomic
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user

        if not cls.is_update(kwargs):
            kwargs["created_by"] = user

        membership_type = kwargs.pop("membership_type", None)

        result = super().mutate_and_get_payload(root, info, **kwargs)

        group = result.group

        if membership_type:
            group.membership_list.membership_type = MembershipList.get_membership_type_from_text(
                membership_type
            )
            group.membership_list.save()

        return cls(group=group)


class GroupUpdateMutation(BaseWriteMutation):
    group = graphene.Field(GroupNode)

    model_class = Group

    class Input:
        id = graphene.ID(required=True)
        name = graphene.String()
        description = graphene.String()
        website = graphene.String()
        email = graphene.String()
        membership_type = graphene.String()

    @classmethod
    @transaction.atomic
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

        membership_type = kwargs.pop("membership_type") if "membership_type" in kwargs else None

        result = super().mutate_and_get_payload(root, info, **kwargs)

        group = result.group

        if membership_type:
            group.membership_list.membership_type = MembershipList.get_membership_type_from_text(
                membership_type
            )
            group.membership_list.save()

        return cls(group=group)


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
