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

from apps.soil_id.graphql.soil_data.queries import (
    DepthDependentSoilDataNode,
    SoilDataNode,
)
from apps.soil_id.graphql.types import DepthIntervalInput


class SoilDataDepthIntervalInputs:
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


class SoilDataInputs:
    depth_interval_preset = SoilDataNode.depth_interval_preset_enum()
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


class SoilDataDepthDependentInputs:
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
