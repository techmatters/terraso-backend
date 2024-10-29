# Copyright © 2024 Technology Matters
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
from graphene_django import DjangoObjectType

from apps.graphql.schema.commons import data_model_excluded_fields
from apps.project_management.graphql.projects import ProjectNode
from apps.soil_id.graphql.types import DepthInterval
from apps.soil_id.models.project_soil_settings import (
    ProjectDepthInterval,
    ProjectSoilSettings,
)


class ProjectSoilSettingsNode(DjangoObjectType):
    class Meta:
        model = ProjectSoilSettings
        exclude = [
            "deleted_at",
            "deleted_by_cascade",
            "id",
            "created_at",
            "updated_at",
        ]

    @classmethod
    def depth_interval_preset_enum(cls):
        return cls._meta.fields["depth_interval_preset"].type.of_type()


class ProjectDepthIntervalNode(DjangoObjectType):
    project = graphene.Field(ProjectNode, source="project__project", required=True)
    depth_interval = graphene.Field(DepthInterval, required=True)

    class Meta:
        model = ProjectDepthInterval
        exclude = data_model_excluded_fields() + [
            "depth_interval_start",
            "depth_interval_end",
        ]

    def resolve_depth_interval(self, info):
        return DepthInterval(start=self.depth_interval_start, end=self.depth_interval_end)
