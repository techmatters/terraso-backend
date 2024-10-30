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
from django.db import transaction

from apps.graphql.schema.commons import BaseAuthenticatedMutation, BaseWriteMutation
from apps.graphql.schema.constants import MutationTypes
from apps.project_management.models.projects import Project
from apps.project_management.permission_rules import Context
from apps.project_management.permission_table import (
    ProjectAction,
    check_project_permission,
)
from apps.soil_id.graphql.soil_project.queries import ProjectSoilSettingsNode
from apps.soil_id.graphql.types import DepthIntervalInput
from apps.soil_id.models.project_soil_settings import (
    ProjectDepthInterval,
    ProjectSoilSettings,
)
from apps.soil_id.models.soil_data import SoilDataDepthInterval


class ProjectSoilSettingsUpdateMutation(BaseWriteMutation):
    project_soil_settings = graphene.Field(ProjectSoilSettingsNode)
    model_class = ProjectSoilSettings

    class Input:
        project_id = graphene.ID(required=True)
        depth_interval_preset = ProjectSoilSettingsNode.depth_interval_preset_enum()
        soil_pit_required = graphene.Boolean()
        slope_required = graphene.Boolean()
        soil_texture_required = graphene.Boolean()
        soil_color_required = graphene.Boolean()
        vertical_cracking_required = graphene.Boolean()
        carbonates_required = graphene.Boolean()
        ph_required = graphene.Boolean()
        soil_organic_carbon_matter_required = graphene.Boolean()
        electrical_conductivity_required = graphene.Boolean()
        sodium_adsorption_ratio_required = graphene.Boolean()
        soil_structure_required = graphene.Boolean()
        land_use_land_cover_required = graphene.Boolean()
        soil_limitations_required = graphene.Boolean()
        photos_required = graphene.Boolean()
        notes_required = graphene.Boolean()

    @classmethod
    def mutate_and_get_payload(cls, root, info, project_id, **kwargs):
        project = cls.get_or_throw(Project, "id", project_id)

        user = info.context.user
        if not check_project_permission(
            user, ProjectAction.UPDATE_REQUIREMENTS, Context(project=project)
        ):
            raise cls.not_allowed(MutationTypes.UPDATE)

        if not hasattr(project, "soil_settings"):
            project.soil_settings = ProjectSoilSettings()

        kwargs["model_instance"] = project.soil_settings

        with transaction.atomic():
            if (
                "depth_interval_preset" in kwargs
                and kwargs["depth_interval_preset"] != project.soil_settings.depth_interval_preset
            ):
                SoilDataDepthInterval.objects.filter(soil_data__site__project=project).delete()
            return super().mutate_and_get_payload(root, info, **kwargs)


class ProjectSoilSettingsUpdateDepthIntervalMutation(BaseWriteMutation):
    project_soil_settings = graphene.Field(ProjectSoilSettingsNode)
    model_class = ProjectDepthInterval
    result_class = ProjectSoilSettings

    class Input:
        project_id = graphene.ID(required=True)
        label = graphene.String()
        depth_interval = graphene.Field(DepthIntervalInput, required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, project_id, depth_interval, **kwargs):
        project = cls.get_or_throw(Project, "id", project_id)

        user = info.context.user
        if not check_project_permission(
            user, ProjectAction.CHANGE_REQUIRED_DEPTH_INTERVAL, Context(project=project)
        ):
            raise cls.not_allowed(MutationTypes.UPDATE)

        if not project.soil_settings or not project.soil_settings.is_custom_preset:
            raise cls.not_allowed(MutationTypes.UPDATE)

        with transaction.atomic():
            if not hasattr(project, "soil_settings"):
                project.soil_settings = ProjectSoilSettings()
                project.soil_settings.save()

            kwargs["model_instance"], _ = project.soil_settings.depth_intervals.get_or_create(
                depth_interval_start=depth_interval["start"],
                depth_interval_end=depth_interval["end"],
            )

            result = super().mutate_and_get_payload(
                root, info, result_instance=project.soil_settings, **kwargs
            )

            return result


class ProjectSoilSettingsDeleteDepthIntervalMutation(BaseAuthenticatedMutation):
    project_soil_settings = graphene.Field(ProjectSoilSettingsNode)

    class Input:
        project_id = graphene.ID(required=True)
        depth_interval = graphene.Field(DepthIntervalInput, required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, project_id, depth_interval, **kwargs):
        project = cls.get_or_throw(Project, "id", project_id)

        user = info.context.user
        if not check_project_permission(
            user, ProjectAction.CHANGE_REQUIRED_DEPTH_INTERVAL, Context(project=project)
        ):
            raise cls.not_allowed(MutationTypes.DELETE)

        if not hasattr(project, "soil_settings"):
            cls.not_found()

        try:
            project_depth_interval = project.soil_settings.depth_intervals.get(
                depth_interval_start=depth_interval["start"],
                depth_interval_end=depth_interval["end"],
            )
        except ProjectDepthInterval.DoesNotExist:
            cls.not_found()

        project_depth_interval.delete()

        return ProjectSoilSettingsDeleteDepthIntervalMutation(
            project_soil_settings=project.soil_settings
        )
