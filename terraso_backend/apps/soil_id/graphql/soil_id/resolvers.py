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

from typing import Optional

from soil_id.us_soil import list_soils, rank_soils

from apps.soil_id.graphql.soil_data import DepthInterval
from apps.soil_id.graphql.soil_id.schema import (
    DataBasedSoilMatch,
    DataBasedSoilMatches,
    EcologicalSite,
    LABColorInput,
    LandCapabilityClass,
    LocationBasedSoilMatch,
    LocationBasedSoilMatches,
    SoilIdDepthDependentData,
    SoilIdInputData,
    SoilIdSoilData,
    SoilInfo,
    SoilMatchInfo,
    SoilSeries,
)
from apps.soil_id.models.depth_dependent_soil_data import DepthDependentSoilData
from apps.soil_id.models.soil_data import SoilData


def resolve_texture(texture: str | float):
    if not isinstance(texture, str) or texture == "":
        return None
    return texture.upper().replace(" ", "_")


def resolve_rock_fragment_volume(rock_fragment_volume: int | float | str):
    if not (isinstance(rock_fragment_volume, float) or isinstance(rock_fragment_volume, int)):
        return None
    elif rock_fragment_volume <= 1:
        return DepthDependentSoilData.RockFragmentVolume.VOLUME_0_1.value
    elif rock_fragment_volume <= 15:
        return DepthDependentSoilData.RockFragmentVolume.VOLUME_1_15.value
    elif rock_fragment_volume <= 35:
        return DepthDependentSoilData.RockFragmentVolume.VOLUME_15_35.value
    elif rock_fragment_volume <= 60:
        return DepthDependentSoilData.RockFragmentVolume.VOLUME_35_60.value
    else:
        return DepthDependentSoilData.RockFragmentVolume.VOLUME_60.value


def resolve_soil_data(soil_match) -> SoilIdSoilData:
    bottom_depths = soil_match["bottom_depth"]
    prev_depth = 0
    depth_dependent_data = [None] * len(bottom_depths)

    for id, bottom_depth in bottom_depths.items():
        depth_dependent_data[int(id)] = SoilIdDepthDependentData(
            depth_interval=DepthInterval(start=prev_depth, end=bottom_depth),
            texture=resolve_texture(soil_match["texture"][id]),
            rock_fragment_volume=resolve_rock_fragment_volume(soil_match["rock_fragments"][id]),
            munsell_color_string=soil_match["munsell"][id],
        )
        prev_depth = bottom_depth

    return SoilIdSoilData(
        slope=soil_match["site"]["siteData"]["slope"], depth_dependent_data=depth_dependent_data
    )


def resolve_ecological_site(ecological_site: dict):
    if ecological_site["ecoclassid"] == "" or ecological_site["ecoclassid"][0] == "":
        return None
    else:
        return EcologicalSite(
            name=ecological_site["ecoclassname"][0],
            id=ecological_site["ecoclassid"][0],
            url=ecological_site["esd_url"][0],
        )


def resolve_soil_info(soil_match: dict):
    soil_id = soil_match["id"]
    site_data = soil_match["site"]["siteData"]

    return SoilInfo(
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
        ecological_site=resolve_ecological_site(soil_match["esd"]["ESD"]),
        soil_data=resolve_soil_data(soil_match),
    )


def resolve_soil_match_info(score: float, rank: str):
    return SoilMatchInfo(score=score, rank=int(rank) - 1)


def resolve_location_based_soil_match(soil_match: dict):
    soil_id = soil_match["id"]
    site_data = soil_match["site"]["siteData"]

    return LocationBasedSoilMatch(
        data_source=site_data["dataSource"],
        distance_to_nearest_map_unit_m=site_data["minCompDistance"],
        match=resolve_soil_match_info(soil_id["score_loc"], soil_id["rank_loc"]),
        soil_info=resolve_soil_info(soil_match),
    )


def resolve_location_matches_from_soil_id_result(soil_list_json: dict):
    matches = []
    for match in soil_list_json["soilList"]:
        if match["id"]["rank_loc"] != "Not Displayed":
            matches.append(resolve_location_based_soil_match(match))
    return LocationBasedSoilMatches(matches=matches)


def resolve_location_based_soil_matches(_parent, _info, latitude: float, longitude: float):
    result = list_soils(lat=latitude, lon=longitude)

    if isinstance(result, str):
        return None

    return resolve_location_matches_from_soil_id_result(result.soil_list_json)


def resolve_data_based_soil_match(soil_matches: list[dict], ranked_match: dict):
    soil_match = [
        match
        for match in soil_matches
        if int(match["site"]["siteData"]["componentID"]) == ranked_match["componentID"]
    ][0]
    site_data = soil_match["site"]["siteData"]

    return DataBasedSoilMatch(
        data_source=site_data["dataSource"],
        distance_to_nearest_map_unit_m=site_data["minCompDistance"],
        location_match=resolve_soil_match_info(ranked_match["score_loc"], ranked_match["rank_loc"]),
        data_match=resolve_soil_match_info(ranked_match["score_data"], ranked_match["rank_data"]),
        combined_match=resolve_soil_match_info(
            ranked_match["score_data_loc"], ranked_match["rank_data_loc"]
        ),
        soil_info=resolve_soil_info(soil_match),
    )


def parse_texture(texture: Optional[DepthDependentSoilData.Texture]):
    if texture is None:
        return None
    return texture.value.replace("_", " ").lower()


def parse_rock_fragment_volume(
    rock_fragment_volume: Optional[DepthDependentSoilData.RockFragmentVolume],
):
    if rock_fragment_volume is None:
        return None
    elif rock_fragment_volume == DepthDependentSoilData.RockFragmentVolume.VOLUME_0_1:
        return "0-1%"
    elif rock_fragment_volume == DepthDependentSoilData.RockFragmentVolume.VOLUME_1_15:
        return "1-15%"
    elif rock_fragment_volume == DepthDependentSoilData.RockFragmentVolume.VOLUME_15_35:
        return "15-35%"
    elif rock_fragment_volume == DepthDependentSoilData.RockFragmentVolume.VOLUME_35_60:
        return "35-60%"
    else:
        return ">60%"


def parse_color_LAB(color_LAB: Optional[LABColorInput]):
    if color_LAB is None:
        return None
    return [color_LAB.L, color_LAB.A, color_LAB.B]


def parse_surface_cracks(surface_cracks: SoilData.SurfaceCracks):
    if surface_cracks is None:
        return None
    return surface_cracks == SoilData.SurfaceCracks.DEEP_VERTICAL_CRACKING


def parse_rank_soils_input_data(data: SoilIdInputData):
    # TODO: pass in values for elevation and bedrock
    inputs = {
        "soilHorizon": [],
        "horizonDepth": [],
        "rfvDepth": [],
        "lab_Color": [],
        "pSlope": data.slope,
        "pElev": None,  # meters
        "bedrock": None,
        "cracks": parse_surface_cracks(data.surface_cracks),
    }

    depths = data.depth_dependent_data
    if len(depths) > 0 and depths[0].depth_interval.start != 0:
        inputs["horizonDepth"].append(depths[0].depth_interval.end)
        inputs["soilHorizon"].append(None)
        inputs["rfvDepth"].append(None)
        inputs["lab_Color"].append(None)
        depths = depths[1:]

    for depth in depths:
        inputs["horizonDepth"].append(depth.depth_interval.end)
        inputs["soilHorizon"].append(parse_texture(depth.texture))
        inputs["rfvDepth"].append(parse_rock_fragment_volume(depth.rock_fragment_volume))
        inputs["lab_Color"].append(parse_color_LAB(depth.color_LAB))

    return inputs


def resolve_data_matches_from_soil_id_result(soil_list_json: dict, rank_json: dict):
    ranked_matches = []
    for ranked_match in rank_json["soilRank"]:
        rankValues = [
            ranked_match["rank_loc"],
            ranked_match["rank_data"],
            ranked_match["rank_data_loc"],
        ]
        if all([value != "Not Displayed" for value in rankValues]):
            ranked_matches.append(
                resolve_data_based_soil_match(soil_list_json["soilList"], ranked_match)
            )

    return DataBasedSoilMatches(matches=ranked_matches)


# to be replaced by actual algorithm output
def resolve_data_based_soil_matches(
    _parent, _info, latitude: float, longitude: float, data: SoilIdInputData
):
    list_result = list_soils(lat=latitude, lon=longitude)
    if isinstance(list_result, str):
        return None

    result = rank_soils(
        lat=latitude,
        lon=longitude,
        list_output_data=list_result,
        **parse_rank_soils_input_data(data),
    )

    return resolve_data_matches_from_soil_id_result(
        soil_list_json=list_result.soil_list_json, rank_json=result
    )
