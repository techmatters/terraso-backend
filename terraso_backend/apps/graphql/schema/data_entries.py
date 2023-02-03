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

import graphene
import structlog
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import Group, Membership
from apps.graphql.exceptions import GraphQLNotAllowedException, GraphQLNotFoundException
from apps.shared_data.models import DataEntry

from .commons import BaseDeleteMutation, BaseWriteMutation, TerrasoConnection
from .constants import MutationTypes

logger = structlog.get_logger(__name__)


class DataEntryNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = DataEntry
        filter_fields = {
            "name": ["icontains"],
            "description": ["icontains"],
            "url": ["icontains"],
            "entry_type": ["in"],
            "resource_type": ["in"],
            "groups__slug": ["exact", "icontains"],
            "groups__id": ["exact"],
        }
        fields = (
            "name",
            "description",
            "entry_type",
            "resource_type",
            "url",
            "size",
            "created_by",
            "created_at",
            "groups",
            "visualizations",
        )
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection

    @classmethod
    def get_queryset(cls, queryset, info):
        user_groups_ids = Membership.objects.filter(
            user=info.context.user, membership_status=Membership.APPROVED
        ).values_list("group", flat=True)
        return queryset.filter(groups__in=user_groups_ids)

    def resolve_url(self, info):
        if self.entry_type == DataEntry.ENTRY_TYPE_FILE:
            return self.signed_url
        return self.url


class DataEntryAddMutation(BaseWriteMutation):
    data_entry = graphene.Field(DataEntryNode)

    model_class = DataEntry

    class Input:
        group_slug = graphene.String(required=True)
        name = graphene.String(required=True)
        url = graphene.String(required=True)
        entry_type = graphene.String(required=True)
        resource_type = graphene.String(required=True)
        description = graphene.String()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user

        if not cls.is_update(kwargs):
            kwargs["created_by"] = user

        if "entry_type" in kwargs:
            kwargs["entry_type"] = DataEntry.get_entry_type_from_text(kwargs["entry_type"])

        group_slug = kwargs.pop("group_slug")
        try:
            group = Group.objects.get(slug=group_slug)
        except Group.DoesNotExist:
            logger.error("Group not found when adding Data Entry", extra={"group_slug": group_slug})
            raise GraphQLNotFoundException(field="group", model_name=DataEntry.__name__)

        result = super().mutate_and_get_payload(root, info, **kwargs)

        result.data_entry.groups.set([group])

        return cls(data_entry=result.data_entry)


class DataEntryUpdateMutation(BaseWriteMutation):
    data_entry = graphene.Field(DataEntryNode)

    model_class = DataEntry

    class Input:
        id = graphene.ID(required=True)
        name = graphene.String()
        description = graphene.String()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        data_entry = DataEntry.objects.get(pk=kwargs["id"])

        if not user.has_perm(DataEntry.get_perm("change"), obj=data_entry):
            logger.info(
                "Attempt to update a DataEntry, but user lacks permission",
                extra={"user_id": user.pk, "data_entry_id": str(data_entry.pk)},
            )
            raise GraphQLNotAllowedException(
                model_name=DataEntry.__name__, operation=MutationTypes.UPDATE
            )

        return super().mutate_and_get_payload(root, info, **kwargs)


class DataEntryDeleteMutation(BaseDeleteMutation):
    data_entry = graphene.Field(DataEntryNode)

    model_class = DataEntry

    class Input:
        id = graphene.ID()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        data_entry = DataEntry.objects.get(pk=kwargs["id"])

        if not user.has_perm(DataEntry.get_perm("delete"), obj=data_entry):
            logger.info(
                "Attempt to delete a DataEntry, but user lacks permission",
                extra={"user_id": user.pk, "data_entry_id": str(data_entry.pk)},
            )
            raise GraphQLNotAllowedException(
                model_name=DataEntry.__name__, operation=MutationTypes.DELETE
            )
        return super().mutate_and_get_payload(root, info, **kwargs)
