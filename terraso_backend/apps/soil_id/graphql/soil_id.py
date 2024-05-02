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

from apps.soil_id.graphql.soil_data import (
    DepthDependentSoilDataNode,
    DepthIntervalInput,
    SoilDataNode,
)


class EcologicalSite(graphene.ObjectType):
    """Information about an ecological site."""

    name = graphene.String(required=True)
    id = graphene.String(required=True)
    url = graphene.String(required=True)


class SoilSeries(graphene.ObjectType):
    """Information about a soil series."""

    name = graphene.String(required=True)
    taxonomy_subgroup = graphene.String(required=True)
    description = graphene.String(required=True)
    full_description_url = graphene.String(required=True)
    data_source = graphene.String(required=True)


class LandCapabilityClass(graphene.ObjectType):
    """Caveat: may want to update these fields to an enum at some point."""

    capability_class = graphene.String(required=True)
    sub_class = graphene.String(required=True)


class SoilInfo(graphene.ObjectType):
    """Provides information about soil at a particular location."""

    soil_series = graphene.Field(SoilSeries, required=True)
    ecological_site = graphene.Field(EcologicalSite, required=False)
    land_capability_class = graphene.Field(LandCapabilityClass, required=True)


class SoilMatch(graphene.ObjectType):
    """The likelihood score and rank within the match group for a particular soil type."""

    score = graphene.Float(required=True)
    rank = graphene.Int(required=True)


class LocationBasedSoilMatch(graphene.ObjectType):
    """A soil match based solely on a coordinate pair."""

    soil_info = graphene.Field(SoilInfo, required=True)
    match = graphene.Field(SoilMatch, required=True)


class LocationBasedSoilMatches(graphene.ObjectType):
    """A ranked group of soil matches based solely on a coordinate pair."""

    matches = graphene.Field(graphene.List(LocationBasedSoilMatch), required=True)


class DataBasedSoilMatch(graphene.ObjectType):
    """A soil match based on a coordinate pair and soil data."""

    soil_info = graphene.Field(SoilInfo, required=True)
    location_match = graphene.Field(SoilMatch, required=True)
    data_match = graphene.Field(SoilMatch, required=True)
    combined_match = graphene.Field(SoilMatch, required=True)


class DataBasedSoilMatches(graphene.ObjectType):
    """A ranked group of soil matches based on a coordinate pair and soil data."""

    matches = graphene.Field(graphene.List(DataBasedSoilMatch), required=True)


class SoilIDInputDepthDependentData(graphene.InputObjectType):
    """Depth dependent data provided to the soil ID algorithm."""

    depth_interval = graphene.Field(DepthIntervalInput, required=True)
    texture = graphene.Field(DepthDependentSoilDataNode.texture_enum())
    rock_fragment_volume = graphene.Field(DepthDependentSoilDataNode.rock_fragment_volume_enum())
    color_hue = graphene.Float()
    color_value = graphene.Float()
    color_chroma = graphene.Float()


class SoilIDInputData(graphene.InputObjectType):
    """Soil data provided to the soil ID algorithm."""

    slope = SoilDataNode.slope_steepness_enum()
    intervals = graphene.Field(graphene.List(SoilIDInputDepthDependentData), required=True)


def resolve_location_based_soil_matches(_parent, _info, latitude: float, longitude: float):
    return LocationBasedSoilMatches(
        matches=[
            LocationBasedSoilMatch(
                match=SoilMatch(score=1.0, rank=0),
                soil_info=SoilInfo(
                    soil_type=SoilSeries(
                        name="Yemassee",
                        taxonomy_subgroup="Aeric Endoaquults",
                        description="The Yemassee series consists of very deep, somewhat poorly drained, moderately permeable, loamy soils that formed in marine sediments. These soils are on terraces and broad flats of the lower Coastal Plain. Slopes range from 0 to 2 percent.",
                        full_description_url="https://casoilresource.lawr.ucdavis.edu/sde/?series=yemassee",
                    ),
                    ecological_site=EcologicalSite(
                        name="Loamy Rise, Moderately Wet",
                        id="R153AY001GA",
                        url="https://edit.jornada.nmsu.edu/catalogs/esd/153A/R153AY001GA",
                    ),
                    land_capability_class=LandCapabilityClass(capability_class="6", sub_class="w"),
                ),
            ),
            LocationBasedSoilMatch(
                match=SoilMatch(score=0.5, rank=1),
                soil_info=SoilInfo(
                    soil_type=SoilSeries(
                        name="Randall",
                        taxonomy_subgroup="Ustic Epiaquerts",
                        description="The Randall series consists of very deep, poorly drained, very slowly permeable soils that formed in clayey lacustrine sediments derived from the Blackwater Draw Formation of Pleistocene age. These nearly level soils are on the floor of playa basins 3 to 15 m (10 to 50 ft) below the surrounding plain and range in size from 10 to more than 150 acres. Slope ranges from 0 to 1 percent. Mean annual precipitation is 483 mm (19 in), and mean annual temperature is 15 degrees C (59 degrees F).",
                        full_description_url="https://casoilresource.lawr.ucdavis.edu/sde/?series=randall",
                    ),
                    land_capability_class=LandCapabilityClass(
                        capability_class="4", sub_class="s-a"
                    ),
                ),
            ),
        ]
    )


def resolve_data_based_soil_matches(
    _parent, _info, latitude: float, longitude: float, soil_data: SoilIDInputData
):
    return DataBasedSoilMatches(
        matches=[
            DataBasedSoilMatch(
                location_match=SoilMatch(score=1.0, rank=0),
                data_match=SoilMatch(score=0.2, rank=1),
                combined_match=SoilMatch(score=0.6, rank=1),
                soil_info=SoilInfo(
                    soil_type=SoilSeries(
                        name="Yemassee",
                        taxonomy_subgroup="Aeric Endoaquults",
                        description="The Yemassee series consists of very deep, somewhat poorly drained, moderately permeable, loamy soils that formed in marine sediments. These soils are on terraces and broad flats of the lower Coastal Plain. Slopes range from 0 to 2 percent.",
                        full_description_url="https://casoilresource.lawr.ucdavis.edu/sde/?series=yemassee",
                    ),
                    land_capability_class=LandCapabilityClass(
                        capability_class="4", sub_class="s-a"
                    ),
                    ecological_site=EcologicalSite(
                        name="Loamy Rise, Moderately Wet",
                        id="R153AY001GA",
                        url="https://edit.jornada.nmsu.edu/catalogs/esd/153A/R153AY001GA",
                    ),
                ),
            ),
            DataBasedSoilMatch(
                location_match=SoilMatch(score=0.5, rank=1),
                data_match=SoilMatch(score=0.75, rank=0),
                combined_match=SoilMatch(score=0.625, rank=0),
                soil_info=SoilInfo(
                    soil_type=SoilSeries(
                        name="Randall",
                        taxonomy_subgroup="Ustic Epiaquerts",
                        description="The Randall series consists of very deep, poorly drained, very slowly permeable soils that formed in clayey lacustrine sediments derived from the Blackwater Draw Formation of Pleistocene age. These nearly level soils are on the floor of playa basins 3 to 15 m (10 to 50 ft) below the surrounding plain and range in size from 10 to more than 150 acres. Slope ranges from 0 to 1 percent. Mean annual precipitation is 483 mm (19 in), and mean annual temperature is 15 degrees C (59 degrees F).",
                        full_description_url="https://casoilresource.lawr.ucdavis.edu/sde/?series=randall",
                    ),
                    land_capability_class=LandCapabilityClass(capability_class="6", sub_class="w"),
                ),
            ),
        ]
    )


class SoilID(graphene.ObjectType):
    """Soil ID algorithm queries."""

    location_based_soil_matches = graphene.Field(
        LocationBasedSoilMatches,
        latitude=graphene.Float(required=True),
        longitude=graphene.Float(required=True),
        resolver=resolve_location_based_soil_matches,
        required=True,
    )

    data_based_soil_matches = graphene.Field(
        DataBasedSoilMatches,
        latitude=graphene.Float(required=True),
        longitude=graphene.Float(required=True),
        data=graphene.Argument(SoilIDInputData, required=True),
        resolver=resolve_data_based_soil_matches,
        required=True,
    )
