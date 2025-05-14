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
from apps.soil_id.graphql.types import DepthInterval, DepthIntervalInput
from apps.soil_id.models.soil_id_cache import SoilIdCache

DataRegion = graphene.Enum.from_enum(SoilIdCache.DataRegion, "SoilIdDataRegionChoices")

class EcologicalSite(graphene.ObjectType):
    """Information about an ecological site."""

    name = graphene.String(required=True)
    id = graphene.String(required=True)
    url = graphene.String(required=True)


class SoilSeries(graphene.ObjectType):
    """Information about a soil series."""

    name = graphene.String(required=True)
    taxonomy_subgroup = graphene.String()
    description = graphene.String(required=True)
    management = graphene.String()
    full_description_url = graphene.String()


class LandCapabilityClass(graphene.ObjectType):
    """Caveat: may want to update these fields to an enum at some point."""

    capability_class = graphene.String(required=True)
    sub_class = graphene.String(required=True)


class SoilIdDepthDependentData(graphene.ObjectType):
    """Depth dependent soil data associated with a soil match output by the soil algorithm."""

    depth_interval = graphene.Field(DepthInterval, required=True)
    texture = DepthDependentSoilDataNode.texture_enum()
    rock_fragment_volume = DepthDependentSoilDataNode.rock_fragment_volume_enum()
    munsell_color_string = graphene.String()


class SoilIdSoilData(graphene.ObjectType):
    """Soil data associated with a soil match output by the soil algorithm."""

    slope = graphene.Float()
    depth_dependent_data = graphene.List(graphene.NonNull(SoilIdDepthDependentData), required=True)


class SoilInfo(graphene.ObjectType):
    """Provides information about soil at a particular location."""

    soil_series = graphene.Field(SoilSeries, required=True)
    ecological_site = graphene.Field(EcologicalSite)
    land_capability_class = graphene.Field(LandCapabilityClass)
    soil_data = graphene.Field(SoilIdSoilData, required=True)


class SoilMatchInfo(graphene.ObjectType):
    """The likelihood score and rank within the match group for a particular soil type."""

    score = graphene.Float(required=True)
    rank = graphene.Int(required=True)


class SoilMatch(graphene.ObjectType):
    """Base class for location/data based soil matches."""

    class Meta:
        abstract = True

    data_source = graphene.String(required=True)
    distance_to_nearest_map_unit_m = graphene.Float(required=True)
    soil_info = graphene.Field(SoilInfo, required=True)


class SoilIdFailureReason(graphene.Enum):
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    ALGORITHM_FAILURE = "ALGORITHM_FAILURE"


class SoilIdFailure(graphene.ObjectType):
    reason = graphene.Field(SoilIdFailureReason, required=True)


class DataBasedSoilMatch(SoilMatch):
    """A soil match based on a coordinate pair and soil data."""

    soil_info = graphene.Field(SoilInfo, required=True)
    location_match = graphene.Field(SoilMatchInfo, required=True)
    data_match = graphene.Field(SoilMatchInfo, required=True)
    combined_match = graphene.Field(SoilMatchInfo, required=True)


class DataBasedSoilMatches(graphene.ObjectType):
    """A ranked group of soil matches based on a coordinate pair and soil data."""

    data_region = DataRegion(required=True)
    matches = graphene.List(graphene.NonNull(DataBasedSoilMatch), required=True)


class DataBasedResult(graphene.Union):
    class Meta:
        types = (DataBasedSoilMatches, SoilIdFailure)


class LABColorInput(graphene.InputObjectType):
    L = graphene.Float(required=True)
    A = graphene.Float(required=True)
    B = graphene.Float(required=True)


class SoilIdInputDepthDependentData(graphene.InputObjectType):
    """Depth dependent data provided to the soil ID algorithm."""

    depth_interval = graphene.Field(DepthIntervalInput, required=True)
    texture = graphene.Field(DepthDependentSoilDataNode.texture_enum())
    rock_fragment_volume = graphene.Field(DepthDependentSoilDataNode.rock_fragment_volume_enum())
    color_LAB = graphene.Field(LABColorInput, name="colorLAB")


class SoilIdInputData(graphene.InputObjectType):
    """Soil data provided to the soil ID algorithm."""

    slope = graphene.Float()
    surface_cracks = SoilDataNode.surface_cracks_enum()
    depth_dependent_data = graphene.List(
        graphene.NonNull(SoilIdInputDepthDependentData), required=True
    )
