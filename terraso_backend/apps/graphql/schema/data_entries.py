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
import rules
import structlog
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.gis.parsers import parse_file_to_geojson
from apps.core.models import Group, Landscape, Membership
from apps.graphql.exceptions import GraphQLNotAllowedException, GraphQLNotFoundException
from apps.shared_data.models import DataEntry
from apps.shared_data.models.data_entries import VALID_TARGET_TYPES
from apps.shared_data.services import data_entry_upload_service

from .commons import BaseDeleteMutation, BaseWriteMutation, TerrasoConnection
from .constants import MutationTypes
from .shared_resources_mixin import SharedResourcesMixin

logger = structlog.get_logger(__name__)


class DataEntryFilterSet(django_filters.FilterSet):
    shared_resources__target__slug = django_filters.CharFilter(
        method="filter_shared_resources_target_slug"
    )
    shared_resources__target_content_type = django_filters.CharFilter(
        method="filter_shared_resources_target_content_type",
    )

    class Meta:
        model = DataEntry
        fields = {
            "name": ["icontains"],
            "description": ["icontains"],
            "url": ["icontains"],
            "entry_type": ["in"],
            "resource_type": ["in"],
            "shared_resources__target_object_id": ["exact"],
        }

    def filter_shared_resources_target_slug(self, queryset, name, value):
        return queryset.filter(
            Q(shared_resources__target_object_id__in=Group.objects.filter(slug=value))
            | Q(shared_resources__target_object_id__in=Landscape.objects.filter(slug=value))
        )

    def filter_shared_resources_target_content_type(self, queryset, name, value):
        return queryset.filter(
            shared_resources__target_content_type=ContentType.objects.get(
                app_label="core", model=value
            )
        ).distinct()


class DataEntryNode(DjangoObjectType, SharedResourcesMixin):
    id = graphene.ID(source="pk", required=True)
    geojson = graphene.JSONString()

    class Meta:
        model = DataEntry
        fields = (
            "name",
            "description",
            "entry_type",
            "resource_type",
            "url",
            "size",
            "created_by",
            "created_at",
            "visualizations",
            "shared_resources",
        )
        interfaces = (relay.Node,)
        filterset_class = DataEntryFilterSet
        connection_class = TerrasoConnection

    @classmethod
    def get_queryset(cls, queryset, info):
        user_pk = getattr(info.context.user, "pk", False)
        user_groups_ids = Membership.objects.filter(
            user__id=user_pk, membership_status=Membership.APPROVED
        ).values_list("group", flat=True)
        user_landscape_ids = Landscape.objects.filter(
            associated_groups__group__memberships__user__id=user_pk,
            associated_groups__group__memberships__membership_status=Membership.APPROVED,
            associated_groups__is_default_landscape_group=True,
        ).values_list("id", flat=True)

        return queryset.filter(
            Q(
                shared_resources__target_content_type=ContentType.objects.get_for_model(Group),
                shared_resources__target_object_id__in=user_groups_ids,
            )
            | Q(
                shared_resources__target_content_type=ContentType.objects.get_for_model(Landscape),
                shared_resources__target_object_id__in=user_landscape_ids,
            )
        )

    def resolve_url(self, info):
        if self.entry_type == DataEntry.ENTRY_TYPE_FILE:
            return self.signed_url
        return self.url

    def resolve_geojson(self, info):
        if f".{self.resource_type}" not in settings.DATA_ENTRY_GIS_TYPES.keys():
            return None
        file = data_entry_upload_service.get_file(self.s3_object_name, "rb")
        try:
            return parse_file_to_geojson(file)
        except ValueError:
            return None


class DataEntryAddMutation(BaseWriteMutation):
    data_entry = graphene.Field(DataEntryNode)

    model_class = DataEntry

    class Input:
        target_type = graphene.String(required=True)
        target_slug = graphene.String(required=True)
        name = graphene.String(required=True)
        url = graphene.String(required=True)
        entry_type = graphene.String(required=True)
        resource_type = graphene.String(required=True)
        description = graphene.String()

    @classmethod
    @transaction.atomic
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user

        target_type = kwargs.pop("target_type")
        target_slug = kwargs.pop("target_slug")

        if target_type not in VALID_TARGET_TYPES:
            logger.error("Invalid target_type provided when adding dataEntry")
            raise GraphQLNotFoundException(
                field="target_type",
                model_name=Group.__name__,
            )

        content_type = ContentType.objects.get(app_label="core", model=target_type)
        model_class = content_type.model_class()

        try:
            target = model_class.objects.get(slug=target_slug)
        except model_class.DoesNotExist:
            logger.error(
                "Target not found when adding dataEntry",
                extra={"target_type": target_type, "target_slug": target_slug},
            )
            raise GraphQLNotFoundException(field="target")

        if not rules.test_rule("allowed_to_add_data_entry", user, target):
            logger.info(
                "Attempt to add a DataEntry, but user lacks permission",
                extra={"user_id": user.pk, "target_id": str(target.pk)},
            )
            raise GraphQLNotAllowedException(
                model_name=DataEntry.__name__, operation=MutationTypes.CREATE
            )

        if not cls.is_update(kwargs):
            kwargs["created_by"] = user

        if "entry_type" in kwargs:
            kwargs["entry_type"] = DataEntry.get_entry_type_from_text(kwargs["entry_type"])

        result = super().mutate_and_get_payload(root, info, **kwargs)

        result.data_entry.shared_resources.create(
            target=target,
        )
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
