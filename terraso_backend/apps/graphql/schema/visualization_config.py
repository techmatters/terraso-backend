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

import csv
import json

import graphene
import openpyxl
import structlog
from django.conf import settings
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.gis.mapbox import create_tileset, get_publish_status, remove_tileset
from apps.core.models import Group, Membership
from apps.graphql.exceptions import GraphQLNotAllowedException
from apps.shared_data.models.data_entries import DataEntry
from apps.shared_data.models.visualization_config import VisualizationConfig
from apps.shared_data.services import data_entry_upload_service

from ..exceptions import GraphQLNotFoundException
from .commons import BaseDeleteMutation, BaseWriteMutation, TerrasoConnection
from .constants import MutationTypes

logger = structlog.get_logger(__name__)


class VisualizationConfigNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = VisualizationConfig
        filter_fields = {
            "slug": ["exact", "icontains"],
            "data_entry__groups__slug": ["exact", "icontains"],
            "data_entry__groups__id": ["exact"],
        }
        fields = (
            "id",
            "slug",
            "title",
            "configuration",
            "created_by",
            "created_at",
            "data_entry",
            "group",
            "mapbox_tileset_id",
        )
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection

    @classmethod
    def get_queryset(cls, queryset, info):
        user_groups_ids = Membership.objects.filter(
            user=info.context.user, membership_status=Membership.APPROVED
        ).values_list("group", flat=True)
        return queryset.filter(data_entry__groups__in=user_groups_ids)

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


def get_rows_from_file(data_entry):
    type = data_entry.resource_type
    if type.startswith("csv"):
        file = data_entry_upload_service.get_file(data_entry.s3_object_name, "rt")
        reader = csv.reader(file)
        return [row for row in reader]
    elif type.startswith("xls"):
        file = data_entry_upload_service.get_file(data_entry.s3_object_name, "rb")
        wb = openpyxl.load_workbook(file)
        ws = wb.active
        return [[cell.value for cell in row] for row in ws.iter_rows()]
    else:
        raise Exception("File type not supported")


def create_mapbox_tileset(data_entry, group_entry, visualization):
    rows = get_rows_from_file(data_entry)
    first_row = rows[0]

    dataset_config = visualization.configuration["datasetConfig"]
    annotate_config = visualization.configuration["annotateConfig"]

    longitude_column = dataset_config["longitude"]
    longitude_index = first_row.index(longitude_column)

    latitude_column = dataset_config["latitude"]
    latitude_index = first_row.index(latitude_column)

    data_points = annotate_config["dataPoints"]
    data_points_indexes = [
        {
            "label": data_point.get("label", data_point["column"]),
            "index": first_row.index(data_point["column"]),
        }
        for data_point in data_points
    ]

    annotation_title = annotate_config.get("annotationTitle")

    title_index = (
        first_row.index(annotation_title)
        if annotation_title and annotation_title in first_row
        else None
    )

    features = []
    for row in rows:
        fields = [
            {
                "label": data_point["label"],
                "value": row[data_point["index"]],
            }
            for data_point in data_points_indexes
        ]

        properties = {
            "title": row[title_index] if title_index else None,
            "fields": json.dumps(fields),
        }

        try:
            longitude = float(row[longitude_index])
            latitude = float(row[latitude_index])
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [longitude, latitude],
                },
                "properties": properties,
            }

            features.append(feature)
        except ValueError:
            continue

    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }
    try:
        title = f"Terraso - {visualization.title}"[:64]
        description = f"Terraso({settings.ENV}) - {group_entry.name} - {visualization.title}"
        id = str(visualization.id).replace("-", "")
        tileset_id = create_tileset(id, geojson, title, description)
        return tileset_id
    except Exception as error:
        raise Exception("Error creating tileset", error)


class VisualizationConfigAddMutation(BaseWriteMutation):
    visualization_config = graphene.Field(VisualizationConfigNode)

    model_class = VisualizationConfig

    class Input:
        title = graphene.String(required=True)
        configuration = graphene.JSONString()
        data_entry_id = graphene.ID(required=True)
        group_id = graphene.ID(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user

        try:
            group_entry = Group.objects.get(id=kwargs["group_id"])
        except Group.DoesNotExist:
            logger.error(
                "Group not found when adding a VisualizationConfig",
                extra={"group_id": kwargs["group_id"]},
            )
            raise GraphQLNotFoundException(field="group", model_name=Group.__name__)

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
        kwargs["group"] = group_entry

        if not cls.is_update(kwargs):
            kwargs["created_by"] = user

        result = super().mutate_and_get_payload(root, info, **kwargs)

        # Create mapbox tileset
        try:
            tileset_id = create_mapbox_tileset(data_entry, group_entry, result.visualization_config)
            result.visualization_config.mapbox_tileset_id = tileset_id
            result.visualization_config.save()
        except Exception as error:
            logger.error(
                "Error creating mapbox tileset",
                extra={"data_entry_id": kwargs["data_entry_id"], "error": str(error)},
            )

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

        # Delete mapbox tileset
        try:
            if visualization_config.mapbox_tileset_id:
                remove_tileset(visualization_config.mapbox_tileset_id)
        except Exception as error:
            logger.error(
                "Error deleting mapbox tileset",
                extra={"data_entry_id": kwargs["data_entry_id"], "error": str(error)},
            )

        # Create mapbox tileset
        try:
            data_entry = visualization_config.data_entry
            group_entry = visualization_config.group
            tileset_id = create_mapbox_tileset(data_entry, group_entry, kwargs)
            kwargs["mapbox_tileset_id"] = tileset_id
        except Exception as error:
            logger.error(
                "Error creating mapbox tileset",
                extra={"data_entry_id": kwargs["data_entry_id"], "error": str(error)},
            )
        return super().mutate_and_get_payload(root, info, **kwargs)


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
        try:
            if visualization_config.mapbox_tileset_id:
                remove_tileset(visualization_config.mapbox_tileset_id)
        except Exception as error:
            logger.error(
                "Error deleting mapbox tileset",
                extra={"data_entry_id": kwargs["data_entry_id"], "error": str(error)},
            )

        return super().mutate_and_get_payload(root, info, **kwargs)
