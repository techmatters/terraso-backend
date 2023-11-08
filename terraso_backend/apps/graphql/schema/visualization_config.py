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
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q, Subquery
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.gis.mapbox import get_publish_status
from apps.core.models import Group, Landscape, Membership
from apps.graphql.exceptions import GraphQLNotAllowedException
from apps.shared_data.models.data_entries import DataEntry
from apps.shared_data.models.visualization_config import VisualizationConfig
from apps.shared_data.visualization_tileset_tasks import (
    start_create_mapbox_tileset_task,
    start_remove_mapbox_tileset_task,
)

from ..exceptions import GraphQLNotFoundException
from . import GroupNode, LandscapeNode
from .commons import BaseDeleteMutation, BaseWriteMutation, TerrasoConnection
from .constants import MutationTypes

logger = structlog.get_logger(__name__)


class VisualizationConfigFilterSet(django_filters.FilterSet):
    data_entry__shared_resources__target__slug = django_filters.CharFilter(
        method="filter_data_entry_shared_resources_target_slug"
    )
    data_entry__shared_resources__target_content_type = django_filters.CharFilter(
        method="filter_data_entry_shared_resources_target_content_type",
    )

    class Meta:
        model = VisualizationConfig
        fields = {
            "slug": ["exact", "icontains"],
            "data_entry__shared_resources__target_object_id": ["exact"],
        }

    def filter_data_entry_shared_resources_target_slug(self, queryset, name, value):
        return queryset.filter(
            Q(data_entry__shared_resources__target_object_id__in=Group.objects.filter(slug=value))
            | Q(
                data_entry__shared_resources__target_object_id__in=Landscape.objects.filter(
                    slug=value
                )
            )
        )

    def filter_data_entry_shared_resources_target_content_type(self, queryset, name, value):
        return queryset.filter(
            data_entry__shared_resources__target_content_type=ContentType.objects.get(
                app_label="core", model=value
            )
        ).distinct()


class OwnerNode(graphene.Union):
    class Meta:
        types = (GroupNode, LandscapeNode)


class VisualizationConfigNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)
    owner = graphene.Field(OwnerNode)

    class Meta:
        model = VisualizationConfig
        fields = (
            "id",
            "slug",
            "title",
            "description",
            "configuration",
            "created_by",
            "created_at",
            "data_entry",
            "mapbox_tileset_id",
        )
        interfaces = (relay.Node,)
        filterset_class = VisualizationConfigFilterSet
        connection_class = TerrasoConnection

    def resolve_mapbox_tileset_id(self, info):
        if self.mapbox_tileset_id is None:
            return None
        if self.mapbox_tileset_status == VisualizationConfig.MAPBOX_TILESET_READY:
            return self.mapbox_tileset_id

        # Check if tileset ready to be published and update status
        published = get_publish_status(self.mapbox_tileset_id)
        if published:
            self.mapbox_tileset_status = VisualizationConfig.MAPBOX_TILESET_READY
            self.save()
            return self.mapbox_tileset_id

    @classmethod
    def get_queryset(cls, queryset, info):
        if info.field_name != "visualizationConfigs":
            return queryset

        user_pk = getattr(info.context.user, "pk", False)

        user_groups_ids = Subquery(
            Group.objects.filter(
                memberships__user__id=user_pk, memberships__membership_status=Membership.APPROVED
            ).values("id")
        )
        user_landscape_ids = Subquery(
            Landscape.objects.filter(
                associated_groups__group__memberships__user__id=user_pk,
                associated_groups__group__memberships__membership_status=Membership.APPROVED,
                associated_groups__is_default_landscape_group=True,
            ).values("id")
        )
        return queryset.filter(
            Q(data_entry__shared_resources__target_object_id__in=user_groups_ids)
            | Q(data_entry__shared_resources__target_object_id__in=user_landscape_ids)
        )


class VisualizationConfigAddMutation(BaseWriteMutation):
    visualization_config = graphene.Field(VisualizationConfigNode)

    model_class = VisualizationConfig

    class Input:
        title = graphene.String(required=True)
        description = graphene.String()
        configuration = graphene.JSONString()
        data_entry_id = graphene.ID(required=True)
        ownerId = graphene.ID(required=True)
        ownerType = graphene.String(required=True)

    @classmethod
    @transaction.atomic
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user

        content_type = ContentType.objects.get(app_label="core", model=kwargs["ownerType"])
        model_class = content_type.model_class()
        try:
            owner = model_class.objects.get(id=kwargs["ownerId"])
        except Group.DoesNotExist:
            logger.error(
                "Target not found when adding a VisualizationConfig",
                extra={
                    "targetId": kwargs["targetId"],
                    "targetType": kwargs["targetType"],
                },
            )
            raise GraphQLNotFoundException(field="target")

        try:
            data_entry = DataEntry.objects.get(id=kwargs["data_entry_id"])
        except DataEntry.DoesNotExist:
            logger.error(
                "DataEntry not found when adding a VisualizationConfig",
                extra={"data_entry_id": kwargs["data_entry_id"]},
            )
            raise GraphQLNotFoundException(field="data_entry", model_name=DataEntry.__name__)

        if not user.has_perm(VisualizationConfig.get_perm("add"), obj=data_entry):
            logger.info(
                "Attempt to add a VisualizationConfig, but user lacks permission",
                extra={"user_id": user.pk, "data_entry_id": str(data_entry.pk)},
            )
            raise GraphQLNotAllowedException(
                model_name=VisualizationConfig.__name__, operation=MutationTypes.CREATE
            )

        kwargs["data_entry"] = data_entry

        if not cls.is_update(kwargs):
            kwargs["created_by"] = user

        kwargs["owner"] = owner

        result = super().mutate_and_get_payload(root, info, **kwargs)

        # Create mapbox tileset
        start_create_mapbox_tileset_task(result.visualization_config.id)

        return cls(visualization_config=result.visualization_config)


class VisualizationConfigUpdateMutation(BaseWriteMutation):
    visualization_config = graphene.Field(VisualizationConfigNode)

    model_class = VisualizationConfig

    class Input:
        id = graphene.ID(required=True)
        configuration = graphene.JSONString()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        visualization_config = VisualizationConfig.objects.get(pk=kwargs["id"])

        if not user.has_perm(VisualizationConfig.get_perm("change"), obj=visualization_config):
            logger.info(
                "Attempt to update a VisualizationConfig, but user lacks permission",
                extra={"user_id": user.pk, "data_entry_id": str(visualization_config.pk)},
            )
            raise GraphQLNotAllowedException(
                model_name=VisualizationConfig.__name__, operation=MutationTypes.UPDATE
            )

        result = super().mutate_and_get_payload(root, info, **kwargs)

        # Create mapbox tileset
        start_create_mapbox_tileset_task(result.visualization_config.id)

        return cls(visualization_config=result.visualization_config)


class VisualizationConfigDeleteMutation(BaseDeleteMutation):
    visualization_config = graphene.Field(VisualizationConfigNode)

    model_class = VisualizationConfig

    class Input:
        id = graphene.ID()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        visualization_config = VisualizationConfig.objects.get(pk=kwargs["id"])

        if not user.has_perm(VisualizationConfig.get_perm("delete"), obj=visualization_config):
            logger.info(
                "Attempt to delete a VisualizationConfig, but user lacks permission",
                extra={"user_id": user.pk, "data_entry_id": str(visualization_config.pk)},
            )
            raise GraphQLNotAllowedException(
                model_name=VisualizationConfig.__name__, operation=MutationTypes.DELETE
            )

        # Delete mapbox tileset
        start_remove_mapbox_tileset_task(visualization_config.mapbox_tileset_id)

        return super().mutate_and_get_payload(root, info, **kwargs)
