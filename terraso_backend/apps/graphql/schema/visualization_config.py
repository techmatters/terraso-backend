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

import secrets

import django_filters
import graphene
import structlog
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Prefetch, Q, Subquery
from graphene import relay
from graphene_django import DjangoObjectType

from apps.collaboration.models import Membership as CollaborationMembership
from apps.core.gis.mapbox import get_publish_status
from apps.core.models import Group, Landscape, SharedResource
from apps.graphql.exceptions import GraphQLNotAllowedException
from apps.graphql.schema.data_entries import DataEntryNode
from apps.graphql.schema.story_maps import StoryMapNode
from apps.shared_data.models.data_entries import DataEntry
from apps.shared_data.models.visualization_config import VisualizationConfig
from apps.shared_data.visualization_tileset_tasks import (
    get_geojson_from_data_entry,
    start_create_mapbox_tileset_task,
    start_remove_mapbox_tileset_task,
)
from apps.story_map.models.story_maps import StoryMap

from ..exceptions import GraphQLNotFoundException
from .commons import BaseDeleteMutation, BaseWriteMutation, TerrasoConnection
from .constants import MutationTypes
from .groups import GroupNode
from .landscapes import LandscapeNode

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
            "readable_id": ["exact"],
            "data_entry__shared_resources__target_object_id": ["exact"],
            "owner_object_id": ["exact"],
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
        types = (GroupNode, LandscapeNode, StoryMapNode)


class VisualizationConfigNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)
    owner = graphene.Field(OwnerNode)
    data_entry = graphene.Field(DataEntryNode)
    geojson = graphene.JSONString()

    class Meta:
        model = VisualizationConfig
        fields = (
            "id",
            "readable_id",
            "slug",
            "title",
            "description",
            "configuration",
            "created_by",
            "created_at",
            "mapbox_tileset_id",
            "mapbox_tileset_status",
        )
        interfaces = (relay.Node,)
        filterset_class = VisualizationConfigFilterSet
        connection_class = TerrasoConnection

    @classmethod
    def get_queryset(cls, queryset, info):
        # Only filter for user memberships if the field is not visualizationConfigs
        # This is because the user can be requesting a visualizations from a parent
        # node, that should be handling the filtering
        if info.field_name != "visualizationConfigs":
            return queryset

        user_pk = getattr(info.context.user, "pk", False)

        [group_subquery, landscape_subquery, storymap_subquery] = [
            Subquery(
                model.objects.filter(
                    membership_list__memberships__deleted_at__isnull=True,
                    membership_list__memberships__user__id=user_pk,
                    membership_list__memberships__membership_status=CollaborationMembership.APPROVED,
                ).values("id")
            )
            for model in [Group, Landscape, StoryMap]
        ]
        storymap_owner_query = Subquery(
            StoryMap.objects.filter(created_by__id=user_pk).values("id")
        )

        return (
            queryset.prefetch_related(
                Prefetch(
                    "data_entry",
                    queryset=DataEntry.objects.prefetch_related(
                        Prefetch(
                            "shared_resources",
                            queryset=SharedResource.objects.prefetch_related("target"),
                        ),
                        Prefetch("created_by"),
                    ),
                ),
                Prefetch("created_by"),
            )
            .filter(
                Q(
                    data_entry__shared_resources__target_object_id__in=group_subquery,
                    data_entry__deleted_at__isnull=True,
                )
                | Q(
                    data_entry__shared_resources__target_object_id__in=landscape_subquery,
                    data_entry__deleted_at__isnull=True,
                )
                | Q(
                    data_entry__shared_resources__target_object_id__in=storymap_subquery,
                    data_entry__deleted_at__isnull=True,
                )
                | Q(
                    data_entry__shared_resources__target_object_id__in=storymap_owner_query,
                    data_entry__deleted_at__isnull=True,
                )
            )
            .distinct()
        )

    def resolve_data_entry(self, info):
        return self.data_entry

    def resolve_mapbox_tileset_id(self, info):
        if self.mapbox_tileset_id is None:
            return None
        if self.mapbox_tileset_status == VisualizationConfig.MAPBOX_TILESET_READY:
            return self.mapbox_tileset_id

        # Check if tileset ready to be published and update status
        if self.mapbox_tileset_id:
            published = get_publish_status(self.mapbox_tileset_id)
            if published:
                self.mapbox_tileset_status = VisualizationConfig.MAPBOX_TILESET_READY
                self.save()

        return self.mapbox_tileset_id

    def resolve_geojson(self, info):
        if (
            self.mapbox_tileset_id is not None
            and self.mapbox_tileset_status == VisualizationConfig.MAPBOX_TILESET_READY
        ):
            return None

        return get_geojson_from_data_entry(self.data_entry, self)


class VisualizationConfigAddMutation(BaseWriteMutation):
    visualization_config = graphene.Field(VisualizationConfigNode)

    model_class = VisualizationConfig

    class Input:
        title = graphene.String(required=True)
        description = graphene.String()
        configuration = graphene.JSONString()
        data_entry_id = graphene.ID(required=True)
        owner_id = graphene.ID(required=True)
        owner_type = graphene.String(required=True)

    @classmethod
    @transaction.atomic
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user

        model_class = VisualizationConfig.get_target_model_class_from_type_name(
            kwargs["owner_type"]
        )

        if model_class is None:
            logger.error("Invalid target_type provided when adding visualizationConfig")
            raise GraphQLNotFoundException(field="ownerId", model_name=VisualizationConfig.__name__)

        try:
            owner = model_class.objects.get(id=kwargs["owner_id"])
        except model_class.DoesNotExist:
            logger.error(
                "Target not found when adding a VisualizationConfig",
                extra={
                    "owner_id": kwargs["owner_id"],
                    "owner_type": kwargs["owner_type"],
                },
            )
            raise GraphQLNotFoundException(field="owner_id")

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

        kwargs["readable_id"] = secrets.token_hex(4)

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
