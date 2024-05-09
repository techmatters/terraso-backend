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
from soil_id.us_soil import list_soils

from apps.soil_id.graphql.soil_data import (
    DepthDependentSoilDataNode,
    DepthInterval,
    DepthIntervalInput,
)
from apps.soil_id.models.depth_dependent_soil_data import DepthDependentSoilData


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
    munsell_color_string = graphene.String()


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
    distance_to_nearest_map_unit_m = graphene.Float(required=True)
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
                    munsell_color_string="10R 5/4",
                ),
                SoilIdDepthDependentData(
                    depth_interval=DepthInterval(start=10, end=15),
                    texture="SILT",
                    rock_fragment_volume="VOLUME_15_35",
                    munsell_color_string="10YR 2/6",
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
                    munsell_color_string="10R 5/4",
                ),
                SoilIdDepthDependentData(
                    depth_interval=DepthInterval(start=10, end=15),
                    texture="SILT",
                    rock_fragment_volume="VOLUME_15_35",
                    munsell_color_string="N 4/",
                ),
            ],
        ),
    ),
]


def resolve_rock_fragment_volume(rock_fragment_volume: int):
    if rock_fragment_volume <= 1:
        return DepthDependentSoilData.RockFragmentVolume.VOLUME_0_1
    elif rock_fragment_volume <= 15:
        return DepthDependentSoilData.RockFragmentVolume.VOLUME_1_15
    elif rock_fragment_volume <= 35:
        return DepthDependentSoilData.RockFragmentVolume.VOLUME_15_35
    elif rock_fragment_volume <= 60:
        return DepthDependentSoilData.RockFragmentVolume.VOLUME_35_60
    else:
        return DepthDependentSoilData.RockFragmentVolume.VOLUME_60


def resolve_soil_data(soil_match):
    bottom_depths = soil_match["bottom_depth"]
    prev_depth = 0
    depth_dependent_data = [None] * len(bottom_depths)

    for id, bottom_depth in bottom_depths.items():
        depth_dependent_data[int(id)] = SoilIdDepthDependentData(
            depth_interval=DepthInterval(start=prev_depth, end=bottom_depth),
            texture=soil_match["texture"][id].upper().replace(" ", "_"),
            rock_fragment_volume=resolve_rock_fragment_volume(soil_match["rock_fragments"][id]),
            munsell_color_string=soil_match["munsell"][id],
        )

    return SoilIdSoilData(
        slope=soil_match["site"]["siteData"]["slope"], depth_dependent_data=depth_dependent_data
    )


def resolve_soil_match(soil_match):
    soil_id = soil_match["id"]
    site_data = soil_match["site"]["siteData"]
    ecological_site = soil_match["esd"]["ESD"]
    if ecological_site["ecoclassid"] == "":
        ecological_site = None
    else:
        ecological_site = EcologicalSite(
            name=ecological_site["ecoclassname"],
            id=ecological_site["ecoclassid"],
            url=ecological_site["esd_url"],
        )

    return LocationBasedSoilMatch(
        data_source=site_data["dataSource"],
        distance_to_nearest_map_unit_m=site_data["minCompDistance"],
        match=SoilMatchInfo(score=soil_id["score_loc"], rank=int(soil_id["rank_loc"]) - 1),
        soil_info=SoilInfo(
            soil_series=SoilSeries(
                name=soil_id["component"],
                taxonomy_subgroup=site_data["taxsubgrp"],
                description=soil_match["site"]["siteDescription"],
                full_description_url=site_data["sdeURL"],
            ),
            land_capability_class=LandCapabilityClass(
                capability_class=site_data["nirrcapcl"],
                sub_class=site_data["nirrcapscl"],
            ),
            ecological_site=ecological_site,
            soil_data=resolve_soil_data(soil_match),
        ),
    )


def resolve_location_based_soil_matches(_parent, _info, latitude: float, longitude: float):
    algorithm_result = list_soils(lat=latitude, lon=longitude, plot_id=None, site_calc=False)

    if isinstance(algorithm_result, str):
        return None

    matches = []
    for match in algorithm_result["soilList"]:
        if match["id"]["rank_loc"] != "Not Displayed":
            matches.append(resolve_soil_match(match))
    return LocationBasedSoilMatches(matches=matches)


# to be replaced by actual algorithm output
def resolve_data_based_soil_matches(
    _parent, _info, latitude: float, longitude: float, data: SoilIdInputData
):
    return DataBasedSoilMatches(
        matches=[
            DataBasedSoilMatch(
                data_source="SSURGO",
                distance_to_nearest_map_unit_m=0.0,
                location_match=SoilMatchInfo(score=1.0, rank=0),
                data_match=SoilMatchInfo(score=0.2, rank=1),
                combined_match=SoilMatchInfo(score=0.6, rank=1),
                soil_info=sample_soil_infos[0],
            ),
            DataBasedSoilMatch(
                data_source="STATSGO",
                distance_to_nearest_map_unit_m=50.0,
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
