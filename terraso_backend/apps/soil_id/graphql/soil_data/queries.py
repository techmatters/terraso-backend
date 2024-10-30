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
from apps.graphql.schema.sites import SiteNode
from apps.soil_id.graphql.types import DepthInterval
from apps.soil_id.models.depth_dependent_soil_data import DepthDependentSoilData
from apps.soil_id.models.soil_data import SoilData, SoilDataDepthInterval


class SoilDataDepthIntervalNode(DjangoObjectType):
    site = graphene.Field(SiteNode, source="soil_data__site", required=True)
    depth_interval = graphene.Field(DepthInterval, required=True)

    class Meta:
        model = SoilDataDepthInterval
        exclude = data_model_excluded_fields() + [
            "soil_data",
            "depth_interval_start",
            "depth_interval_end",
        ]

    def resolve_depth_interval(self, info):
        return DepthInterval(start=self.depth_interval_start, end=self.depth_interval_end)


class SoilDataNode(DjangoObjectType):
    class Meta:
        model = SoilData
        exclude = data_model_excluded_fields()

    @classmethod
    def down_slope_enum(cls):
        return cls._meta.fields["down_slope"].type()

    @classmethod
    def cross_slope_enum(cls):
        return cls._meta.fields["cross_slope"].type()

    @classmethod
    def slope_landscape_position_enum(cls):
        return cls._meta.fields["slope_landscape_position"].type()

    @classmethod
    def slope_steepness_enum(cls):
        return cls._meta.fields["slope_steepness_select"].type()

    @classmethod
    def surface_cracks_enum(cls):
        return cls._meta.fields["surface_cracks_select"].type()

    @classmethod
    def surface_salt_enum(cls):
        return cls._meta.fields["surface_salt_select"].type()

    @classmethod
    def flooding_enum(cls):
        return cls._meta.fields["flooding_select"].type()

    @classmethod
    def lime_requirements_enum(cls):
        return cls._meta.fields["lime_requirements_select"].type()

    @classmethod
    def surface_stoniness_enum(cls):
        return cls._meta.fields["surface_stoniness_select"].type()

    @classmethod
    def water_table_depth_enum(cls):
        return cls._meta.fields["water_table_depth_select"].type()

    @classmethod
    def soil_depth_enum(cls):
        return cls._meta.fields["soil_depth_select"].type()

    @classmethod
    def land_cover_enum(cls):
        return cls._meta.fields["land_cover_select"].type()

    @classmethod
    def grazing_enum(cls):
        return cls._meta.fields["grazing_select"].type()

    @classmethod
    def depth_interval_preset_enum(cls):
        return cls._meta.fields["depth_interval_preset"].type.of_type()


class DepthDependentSoilDataNode(DjangoObjectType):
    site = graphene.Field(SiteNode, source="soil_data__site", required=True)
    depth_interval = graphene.Field(DepthInterval, required=True)

    class Meta:
        model = DepthDependentSoilData
        exclude = data_model_excluded_fields() + [
            "soil_data",
            "depth_interval_start",
            "depth_interval_end",
        ]

    def resolve_depth_interval(self, info):
        return DepthInterval(start=self.depth_interval_start, end=self.depth_interval_end)

    @classmethod
    def texture_enum(cls):
        return cls._meta.fields["texture"].type()

    @classmethod
    def rock_fragment_volume_enum(cls):
        return cls._meta.fields["rock_fragment_volume"].type()

    @classmethod
    def color_photo_soil_condition_enum(cls):
        return cls._meta.fields["color_photo_soil_condition"].type()

    @classmethod
    def color_photo_lighting_condition_enum(cls):
        return cls._meta.fields["color_photo_lighting_condition"].type()

    @classmethod
    def conductivity_test_enum(cls):
        return cls._meta.fields["conductivity_test"].type()

    @classmethod
    def conductivity_unit_enum(cls):
        return cls._meta.fields["conductivity_unit"].type()

    @classmethod
    def structure_enum(cls):
        return cls._meta.fields["structure"].type()

    @classmethod
    def ph_testing_solution_enum(cls):
        return cls._meta.fields["ph_testing_solution"].type()

    @classmethod
    def ph_testing_method_enum(cls):
        return cls._meta.fields["ph_testing_method"].type()

    @classmethod
    def soil_organic_carbon_testing_enum(cls):
        return cls._meta.fields["soil_organic_carbon_testing"].type()

    @classmethod
    def soil_organic_matter_testing_enum(cls):
        return cls._meta.fields["soil_organic_matter_testing"].type()

    @classmethod
    def carbonates_enum(cls):
        return cls._meta.fields["carbonates"].type()
