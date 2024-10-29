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
from apps.project_management.models.sites import Site
from apps.project_management.permission_rules import Context
from apps.project_management.permission_table import SiteAction, check_site_permission
from apps.soil_id.graphql.soil_data.queries import (
    DepthDependentSoilDataNode,
    SoilDataDepthIntervalNode,
    SoilDataNode,
)
from apps.soil_id.graphql.types import DepthIntervalInput
from apps.soil_id.models.depth_dependent_soil_data import DepthDependentSoilData
from apps.soil_id.models.soil_data import SoilData, SoilDataDepthInterval


class SoilDataUpdateDepthIntervalMutation(BaseWriteMutation):
    soil_data = graphene.Field(SoilDataNode)
    model_class = SoilDataDepthIntervalNode
    result_class = SoilData

    class Input:
        site_id = graphene.ID(required=True)
        label = graphene.String()
        depth_interval = graphene.Field(DepthIntervalInput, required=True)
        soil_texture_enabled = graphene.Boolean()
        soil_color_enabled = graphene.Boolean()
        carbonates_enabled = graphene.Boolean()
        ph_enabled = graphene.Boolean()
        soil_organic_carbon_matter_enabled = graphene.Boolean()
        electrical_conductivity_enabled = graphene.Boolean()
        sodium_adsorption_ratio_enabled = graphene.Boolean()
        soil_structure_enabled = graphene.Boolean()
        apply_to_intervals = graphene.Field(graphene.List(graphene.NonNull(DepthIntervalInput)))

    @classmethod
    def mutate_and_get_payload(
        cls,
        root,
        info,
        site_id,
        depth_interval,
        apply_to_intervals=None,
        **kwargs,
    ):
        site = cls.get_or_throw(Site, "id", site_id)

        user = info.context.user
        if not check_site_permission(user, SiteAction.UPDATE_DEPTH_INTERVAL, Context(site=site)):
            raise cls.not_allowed(MutationTypes.UPDATE)

        with transaction.atomic():
            if not hasattr(site, "soil_data"):
                site.soil_data = SoilData()
                site.soil_data.save()

            kwargs["model_instance"], _ = site.soil_data.depth_intervals.get_or_create(
                depth_interval_start=depth_interval["start"],
                depth_interval_end=depth_interval["end"],
            )

            result = super().mutate_and_get_payload(
                root, info, result_instance=site.soil_data, **kwargs
            )
            if apply_to_intervals:
                for key in ("label", "model_instance"):
                    kwargs.pop(key, "")
                # TODO: Would be better to do bulk create, but can't get that to work:
                # "there is no unique or exclusion constraint matching the ON CONFLICT
                # specification"
                for interval in apply_to_intervals:
                    soil_interval, _ = SoilDataDepthInterval.objects.get_or_create(
                        soil_data=site.soil_data,
                        depth_interval_start=interval.start,
                        depth_interval_end=interval.end,
                    )
                    for key, value in kwargs.items():
                        setattr(soil_interval, key, value)
                    soil_interval.save()

                result.soil_data.refresh_from_db()

        return result


class SoilDataDeleteDepthIntervalMutation(BaseAuthenticatedMutation):
    soil_data = graphene.Field(SoilDataNode)

    class Input:
        site_id = graphene.ID(required=True)
        depth_interval = graphene.Field(DepthIntervalInput, required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, site_id, depth_interval, **kwargs):
        site = cls.get_or_throw(Site, "id", site_id)

        user = info.context.user
        if not check_site_permission(user, SiteAction.UPDATE_DEPTH_INTERVAL, Context(site=site)):
            raise cls.not_allowed(MutationTypes.DELETE)

        if not hasattr(site, "soil_data"):
            cls.not_found()

        try:
            depth_interval = site.soil_data.depth_intervals.get(
                depth_interval_start=depth_interval["start"],
                depth_interval_end=depth_interval["end"],
            )
        except SoilDataDepthInterval.DoesNotExist:
            cls.not_found()

        depth_interval.delete()

        return SoilDataDeleteDepthIntervalMutation(soil_data=site.soil_data)


class SoilDataUpdateMutation(BaseWriteMutation):
    soil_data = graphene.Field(SoilDataNode)
    model_class = SoilData

    class Input:
        site_id = graphene.ID(required=True)
        down_slope = SoilDataNode.down_slope_enum()
        cross_slope = SoilDataNode.cross_slope_enum()
        bedrock = graphene.Int()
        slope_landscape_position = SoilDataNode.slope_landscape_position_enum()
        slope_aspect = graphene.Int()
        slope_steepness_select = SoilDataNode.slope_steepness_enum()
        slope_steepness_percent = graphene.Int()
        slope_steepness_degree = graphene.Int()
        surface_cracks_select = SoilDataNode.surface_cracks_enum()
        surface_salt_select = SoilDataNode.surface_salt_enum()
        flooding_select = SoilDataNode.flooding_enum()
        lime_requirements_select = SoilDataNode.lime_requirements_enum()
        surface_stoniness_select = SoilDataNode.surface_stoniness_enum()
        water_table_depth_select = SoilDataNode.water_table_depth_enum()
        soil_depth_select = SoilDataNode.soil_depth_enum()
        land_cover_select = SoilDataNode.land_cover_enum()
        grazing_select = SoilDataNode.grazing_enum()
        depth_interval_preset = SoilDataNode.depth_interval_preset_enum()

    @classmethod
    def mutate_and_get_payload(cls, root, info, site_id, **kwargs):
        site = cls.get_or_throw(Site, "id", site_id)

        user = info.context.user
        if not check_site_permission(user, SiteAction.ENTER_DATA, Context(site=site)):
            raise cls.not_allowed(MutationTypes.UPDATE)

        if not hasattr(site, "soil_data"):
            site.soil_data = SoilData()

        kwargs["model_instance"] = site.soil_data

        with transaction.atomic():
            if (
                "depth_interval_preset" in kwargs
                and kwargs["depth_interval_preset"] != site.soil_data.depth_interval_preset
            ):
                site.soil_data.depth_intervals.all().delete()
            result = super().mutate_and_get_payload(root, info, **kwargs)
        return result


class DepthDependentSoilDataUpdateMutation(BaseWriteMutation):
    soil_data = graphene.Field(SoilDataNode)
    model_class = DepthDependentSoilData
    result_class = SoilData

    class Input:
        site_id = graphene.ID(required=True)
        depth_interval = graphene.Field(DepthIntervalInput, required=True)
        texture = DepthDependentSoilDataNode.texture_enum()
        clay_percent = graphene.Int()
        rock_fragment_volume = DepthDependentSoilDataNode.rock_fragment_volume_enum()
        color_hue = graphene.Float()
        color_value = graphene.Float()
        color_chroma = graphene.Float()
        color_photo_used = graphene.Boolean()
        color_photo_soil_condition = DepthDependentSoilDataNode.color_photo_soil_condition_enum()
        color_photo_lighting_condition = (
            DepthDependentSoilDataNode.color_photo_lighting_condition_enum()
        )
        conductivity = graphene.Decimal()
        conductivity_test = DepthDependentSoilDataNode.conductivity_test_enum()
        conductivity_unit = DepthDependentSoilDataNode.conductivity_unit_enum()
        structure = DepthDependentSoilDataNode.structure_enum()
        ph = graphene.Decimal()
        ph_testing_solution = DepthDependentSoilDataNode.ph_testing_solution_enum()
        ph_testing_method = DepthDependentSoilDataNode.ph_testing_method_enum()
        soil_organic_carbon = graphene.Decimal()
        soil_organic_matter = graphene.Decimal()
        soil_organic_carbon_testing = DepthDependentSoilDataNode.soil_organic_carbon_testing_enum()
        soil_organic_matter_testing = DepthDependentSoilDataNode.soil_organic_matter_testing_enum()
        sodium_absorption_ratio = graphene.Decimal()
        carbonates = DepthDependentSoilDataNode.carbonates_enum()

    @classmethod
    def mutate_and_get_payload(cls, root, info, site_id, depth_interval, **kwargs):
        site = cls.get_or_throw(Site, "id", site_id)

        user = info.context.user
        if not check_site_permission(user, SiteAction.ENTER_DATA, Context(site=site)):
            raise cls.not_allowed(MutationTypes.UPDATE)

        with transaction.atomic():
            if not hasattr(site, "soil_data"):
                site.soil_data = SoilData()
                site.soil_data.save()

            kwargs["model_instance"], _ = site.soil_data.depth_dependent_data.get_or_create(
                depth_interval_start=depth_interval["start"],
                depth_interval_end=depth_interval["end"],
            )

            return super().mutate_and_get_payload(
                root, info, result_instance=site.soil_data, **kwargs
            )
