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
    DepthInterval,
    DepthIntervalInput,
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


class LandCapabilityClass(graphene.ObjectType):
    """Caveat: may want to update these fields to an enum at some point."""

    capability_class = graphene.String(required=True)
    sub_class = graphene.String(required=True)


class SoilIdDepthDependentData(graphene.ObjectType):
    """Depth dependent soil data associated with a soil match output by the soil algorithm."""

    depth_interval = graphene.Field(DepthInterval, required=True)
    texture = DepthDependentSoilDataNode.texture_enum()
    rock_fragment_volume = DepthDependentSoilDataNode.rock_fragment_volume_enum()
    color_hue = graphene.Float()
    color_value = graphene.Float()
    color_chroma = graphene.Float()


class SoilIdSoilData(graphene.ObjectType):
    """Soil data associated with a soil match output by the soil algorithm."""

    slope = graphene.Float()
    depth_dependent_data = graphene.List(graphene.NonNull(SoilIdDepthDependentData), required=True)


class SoilInfo(graphene.ObjectType):
    """Provides information about soil at a particular location."""

    soil_series = graphene.Field(SoilSeries, required=True)
    ecological_site = graphene.Field(EcologicalSite, required=False)
    land_capability_class = graphene.Field(LandCapabilityClass, required=True)
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
    in_map_unit = graphene.Boolean(required=True)
    soil_info = graphene.Field(SoilInfo, required=True)


class LocationBasedSoilMatch(SoilMatch):
    """A soil match based solely on a coordinate pair."""

    match = graphene.Field(SoilMatchInfo, required=True)


class LocationBasedSoilMatches(graphene.ObjectType):
    """A ranked group of soil matches based solely on a coordinate pair."""

    matches = graphene.List(graphene.NonNull(LocationBasedSoilMatch), required=True)


class DataBasedSoilMatch(SoilMatch):
    """A soil match based on a coordinate pair and soil data."""

    soil_info = graphene.Field(SoilInfo, required=True)
    location_match = graphene.Field(SoilMatchInfo, required=True)
    data_match = graphene.Field(SoilMatchInfo, required=True)
    combined_match = graphene.Field(SoilMatchInfo, required=True)


class DataBasedSoilMatches(graphene.ObjectType):
    """A ranked group of soil matches based on a coordinate pair and soil data."""

    matches = graphene.List(graphene.NonNull(DataBasedSoilMatch), required=True)


class SoilIdInputDepthDependentData(graphene.InputObjectType):
    """Depth dependent data provided to the soil ID algorithm."""

    depth_interval = graphene.Field(DepthIntervalInput, required=True)
    texture = graphene.Field(DepthDependentSoilDataNode.texture_enum())
    rock_fragment_volume = graphene.Field(DepthDependentSoilDataNode.rock_fragment_volume_enum())
    color_hue = graphene.Float()
    color_value = graphene.Float()
    color_chroma = graphene.Float()


class SoilIdInputData(graphene.InputObjectType):
    """Soil data provided to the soil ID algorithm."""

    slope = graphene.Float()
    depth_dependent_data = graphene.List(
        graphene.NonNull(SoilIdInputDepthDependentData), required=True
    )


sample_soil_infos = [
    SoilInfo(
        soil_series=SoilSeries(
            name="Yemassee",
            taxonomy_subgroup="Aeric Endoaquults",
            description="The Yemassee series consists of very deep, somewhat poorly drained, moderately permeable, loamy soils that formed in marine sediments. These soils are on terraces and broad flats of the lower Coastal Plain. Slopes range from 0 to 2 percent.",  # noqa: E501   <- flake8 ignore line length
            full_description_url="https://casoilresource.lawr.ucdavis.edu/sde/?series=yemassee",  # noqa: E501   <- flake8 ignore line length
        ),
        ecological_site=EcologicalSite(
            name="Loamy Rise, Moderately Wet",
            id="R153AY001GA",
            url="https://edit.jornada.nmsu.edu/catalogs/esd/153A/R153AY001GA",
        ),
        land_capability_class=LandCapabilityClass(capability_class="6", sub_class="w"),
        soil_data=SoilIdSoilData(
            slope=0.5,
            depth_dependent_data=[
                SoilIdDepthDependentData(
                    depth_interval=DepthInterval(start=0, end=10),
                    texture="CLAY_LOAM",
                    rock_fragment_volume="VOLUME_1_15",
                    color_hue=10.0,
                    color_value=5.0,
                    color_chroma=4.0,
                ),
                SoilIdDepthDependentData(
                    depth_interval=DepthInterval(start=10, end=15),
                    texture="SILT",
                    rock_fragment_volume="VOLUME_15_35",
                    color_hue=15.0,
                    color_value=2.0,
                    color_chroma=0.0,
                ),
            ],
        ),
    ),
    SoilInfo(
        soil_series=SoilSeries(
            name="Randall",
            taxonomy_subgroup="Ustic Epiaquerts",
            description="The Randall series consists of very deep, poorly drained, very slowly permeable soils that formed in clayey lacustrine sediments derived from the Blackwater Draw Formation of Pleistocene age. These nearly level soils are on the floor of playa basins 3 to 15 m (10 to 50 ft) below the surrounding plain and range in size from 10 to more than 150 acres. Slope ranges from 0 to 1 percent. Mean annual precipitation is 483 mm (19 in), and mean annual temperature is 15 degrees C (59 degrees F).",  # noqa: E501   <- flake8 ignore line length
            full_description_url="https://casoilresource.lawr.ucdavis.edu/sde/?series=randall",  # noqa: E501   <- flake8 ignore line length
        ),
        land_capability_class=LandCapabilityClass(capability_class="4", sub_class="s-a"),
        soil_data=SoilIdSoilData(
            slope=0.5,
            depth_dependent_data=[
                SoilIdDepthDependentData(
                    depth_interval=DepthInterval(start=0, end=10),
                    texture="CLAY_LOAM",
                    rock_fragment_volume="VOLUME_1_15",
                    color_hue=10.0,
                    color_value=5.0,
                    color_chroma=4.0,
                ),
                SoilIdDepthDependentData(
                    depth_interval=DepthInterval(start=10, end=15),
                    texture="SILT",
                    rock_fragment_volume="VOLUME_15_35",
                    color_hue=15.0,
                    color_value=2.0,
                    color_chroma=0.0,
                ),
            ],
        ),
    ),
]


# to be replaced by actual algorithm output
def resolve_location_based_soil_matches(_parent, _info, latitude: float, longitude: float):
    return LocationBasedSoilMatches(
        matches=[
            LocationBasedSoilMatch(
                data_source="SSURGO",
                in_map_unit=True,
                match=SoilMatchInfo(score=1.0, rank=0),
                soil_info=sample_soil_infos[0],
            ),
            LocationBasedSoilMatch(
                data_source="STATSGO",
                in_map_unit=False,
                match=SoilMatchInfo(score=0.5, rank=1),
                soil_info=sample_soil_infos[1],
            ),
        ]
    )


# to be replaced by actual algorithm output
def resolve_data_based_soil_matches(
    _parent, _info, latitude: float, longitude: float, data: SoilIdInputData
):
    return DataBasedSoilMatches(
        matches=[
            DataBasedSoilMatch(
                data_source="SSURGO",
                in_map_unit=True,
                location_match=SoilMatchInfo(score=1.0, rank=0),
                data_match=SoilMatchInfo(score=0.2, rank=1),
                combined_match=SoilMatchInfo(score=0.6, rank=1),
                soil_info=sample_soil_infos[0],
            ),
            DataBasedSoilMatch(
                data_source="STATSGO",
                in_map_unit=False,
                location_match=SoilMatchInfo(score=0.5, rank=1),
                data_match=SoilMatchInfo(score=0.75, rank=0),
                combined_match=SoilMatchInfo(score=0.625, rank=0),
                soil_info=sample_soil_infos[1],
            ),
        ]
    )


class SoilId(graphene.ObjectType):
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
        data=graphene.Argument(SoilIdInputData, required=True),
        resolver=resolve_data_based_soil_matches,
        required=True,
    )


def resolve_soil_id(parent, info):
    return SoilId()


soil_id = graphene.Field(
    SoilId, required=True, resolver=resolve_soil_id, description="Soil ID algorithm Queries"
)
