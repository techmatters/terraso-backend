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

import math
import traceback
from typing import Optional

import psycopg
import structlog
from soil_id import us_soil
from soil_id import global_soil
from soil_id.utils import find_region_for_location

from apps.soil_id.graphql.soil_id.types import (
    DataBasedSoilMatch,
    DataBasedSoilMatches,
    EcologicalSite,
    LABColorInput,
    LandCapabilityClass,
    SoilIdDepthDependentData,
    SoilIdFailure,
    SoilIdFailureReason,
    SoilIdInputData,
    SoilIdSoilData,
    SoilInfo,
    SoilMatchInfo,
    SoilSeries,
)
from apps.soil_id.graphql.types import DepthInterval
from apps.soil_id.models.depth_dependent_soil_data import DepthDependentSoilData
from apps.soil_id.models.soil_data import SoilData
from apps.soil_id.models.soil_id_cache import SoilIdCache
from config.settings import SOIL_ID_DATABASE_URL

logger = structlog.get_logger(__name__)

_soil_id_database_connection = None


def soil_id_database_connection():
    global _soil_id_database_connection
    if _soil_id_database_connection is None:
        _soil_id_database_connection = psycopg.connect(SOIL_ID_DATABASE_URL)

    return _soil_id_database_connection


def resolve_texture(texture: str | float):
    if not isinstance(texture, str) or texture == "" or texture.upper() == "UNKNOWN":
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
    depth_dependent_data = []

    for id, bottom_depth in sorted(bottom_depths.items(), key=lambda item: item[1]):
        depth_dependent_data.append(
            SoilIdDepthDependentData(
                depth_interval=DepthInterval(start=prev_depth, end=bottom_depth),
                texture=resolve_texture(soil_match["texture"][id]),
                rock_fragment_volume=resolve_rock_fragment_volume(soil_match["rock_fragments"][id]),
                munsell_color_string=soil_match["munsell"][id] if "munsell" in soil_match else None,
            )
        )
        prev_depth = bottom_depth

    slope = (
        soil_match["site"]["siteData"]["slope"]
        if "slope" in soil_match["site"]["siteData"]
        else None
    )
    if slope == "":
        slope = None

    return SoilIdSoilData(slope=slope, depth_dependent_data=depth_dependent_data)


def resolve_ecological_site(soil_match: dict):
    if "esd" not in soil_match:
        return None

    ecological_site = soil_match["esd"]["ESD"]
    if ecological_site["ecoclassid"] == "" or ecological_site["ecoclassid"][0] == "":
        return None
    else:
        return EcologicalSite(
            name=ecological_site["ecoclassname"][0],
            id=ecological_site["ecoclassid"][0],
            url=ecological_site["edit_url"][0],
        )


def resolve_land_capability_class(site_data: dict):
    def resolve_lcc_value(value):
        # note that the soil ID algorithm also sometimes returns the _strings_ "None" or "nan"
        if not isinstance(value, str) or value == "None" or value == "nan":
            return ""
        return value

    if "nirrcapcl" not in site_data:
        return None

    return LandCapabilityClass(
        capability_class=resolve_lcc_value(site_data["nirrcapcl"]),
        sub_class=resolve_lcc_value(site_data["nirrcapscl"]),
    )


def resolve_soil_info(soil_match: dict):
    soil_id = soil_match["id"]
    site_data = soil_match["site"]["siteData"]

    taxonomy_subgroup = site_data["taxsubgrp"] if "taxsubgrp" in site_data else None
    full_description_url = site_data["sdeURL"] if "sdeURL" in site_data else None
    description = soil_match["site"]["siteDescription"]
    if not isinstance(description, str):
        description = None

    return SoilInfo(
        soil_series=SoilSeries(
            name=soil_id["component"],
            taxonomy_subgroup=taxonomy_subgroup,
            description=description,
            full_description_url=full_description_url,
        ),
        land_capability_class=resolve_land_capability_class(site_data),
        ecological_site=resolve_ecological_site(soil_match),
        soil_data=resolve_soil_data(soil_match),
    )


def resolve_soil_match_info(score: Optional[float], rank: Optional[str]):
    if score is None or rank is None or rank == "":
        return None
    return SoilMatchInfo(score=score, rank=int(rank) - 1)


def resolve_list_output_failure(
    list_output: us_soil.SoilListOutputData | global_soil.SoilListOutputData | str,
):
    if isinstance(list_output, us_soil.SoilListOutputData) or isinstance(
        list_output, global_soil.SoilListOutputData
    ):
        return None
    elif isinstance(list_output, str):
        return SoilIdFailureReason.DATA_UNAVAILABLE
    else:
        return SoilIdFailureReason.ALGORITHM_FAILURE


def clean_soil_list_json(obj):
    if isinstance(obj, float) and math.isnan(obj):
        return None
    elif isinstance(obj, dict):
        return dict((k, clean_soil_list_json(v)) for k, v in obj.items())
    elif isinstance(obj, (list, set, tuple)):
        return list(map(clean_soil_list_json, obj))
    return obj


def get_cached_list_soils_output(latitude, longitude):
    cached_result = SoilIdCache.get_data(latitude=latitude, longitude=longitude)

    if cached_result is None:
        data_region = parse_data_region(find_region_for_location(lat=latitude, lon=longitude))
        if data_region is None:
            list_output = "DATA_UNAVAILABLE"
        elif data_region == SoilIdCache.DataRegion.US:
            list_output = us_soil.list_soils(lat=latitude, lon=longitude)
        elif data_region == SoilIdCache.DataRegion.GLOBAL:
            list_output = global_soil.list_soils_global(
                lat=latitude,
                lon=longitude,
                connection=soil_id_database_connection(),
                buffer_dist=30000,
            )
        else:
            raise ValueError(f"Unknown data region: {data_region}")

        failure_reason = resolve_list_output_failure(list_output)

        if failure_reason is not None:
            list_output = failure_reason.value
        else:
            list_output.soil_list_json = clean_soil_list_json(list_output.soil_list_json)

        SoilIdCache.save_data(
            latitude=latitude, longitude=longitude, data=list_output, data_region=data_region
        )

        if failure_reason is not None:
            return list_output
        else:
            return data_region, list_output
    else:
        return cached_result


def resolve_data_based_soil_match(
    data_region: SoilIdCache.DataRegion, soil_matches: list[dict], ranked_match: dict
):
    soil_match = [
        match
        for match in soil_matches
        if int(match["site"]["siteData"]["componentID"]) == ranked_match["componentID"]
    ][0]
    site_data = soil_match["site"]["siteData"]

    if data_region == SoilIdCache.DataRegion.GLOBAL:
        data_source = "HWSD"
    else:
        data_source = site_data["dataSource"]

    return DataBasedSoilMatch(
        data_source=data_source,
        distance_to_nearest_map_unit_m=site_data["minCompDistance"],
        location_match=resolve_soil_match_info(ranked_match["score_loc"], ranked_match["rank_loc"]),
        data_match=resolve_soil_match_info(ranked_match["score_data"], ranked_match["rank_data"]),
        combined_match=resolve_soil_match_info(
            ranked_match["score_data_loc"], ranked_match["rank_data_loc"]
        ),
        soil_info=resolve_soil_info(soil_match),
    )


def parse_data_region(data_region: Optional[str]):
    if data_region is None:
        return None
    elif data_region == "US":
        return SoilIdCache.DataRegion.US
    elif data_region == "Global":
        return SoilIdCache.DataRegion.GLOBAL
    else:
        raise ValueError(f"Unknown data region: {data_region}")


# Argument type hint would be DepthDependentSoilDataNode.texture_enum() if that were allowed :)
def parse_texture(texture):
    if texture is None:
        return None
    return texture.value.replace("_", " ").lower()


# Argument type hint would be DepthDependentSoilDataNode.rock_fragment_volume_enum() if that were allowed :)
def parse_rock_fragment_volume(rock_fragment_volume):
    if rock_fragment_volume is None:
        return None
    elif rock_fragment_volume.value == DepthDependentSoilData.RockFragmentVolume.VOLUME_0_1.value:
        return "0-1%"
    elif rock_fragment_volume.value == DepthDependentSoilData.RockFragmentVolume.VOLUME_1_15.value:
        return "1-15%"
    elif rock_fragment_volume.value == DepthDependentSoilData.RockFragmentVolume.VOLUME_15_35.value:
        return "15-35%"
    elif rock_fragment_volume.value == DepthDependentSoilData.RockFragmentVolume.VOLUME_35_60.value:
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


def parse_rank_soils_input_data(
    data: Optional[SoilIdInputData], data_region: SoilIdCache.DataRegion
):
    # TODO: pass in values for elevation and bedrock
    inputs = {
        "soilHorizon": [],
        "rfvDepth": [],
        "lab_Color": [],
        "bedrock": None,
        "cracks": None,
    }

    if data_region == SoilIdCache.DataRegion.US:
        inputs["pElev"] = None
        inputs["pSlope"] = None

    inputs["topDepth"] = []
    inputs["bottomDepth"] = []

    if data is None:
        return inputs

    inputs["cracks"] = parse_surface_cracks(data.surface_cracks)

    if data_region == SoilIdCache.DataRegion.US:
        inputs["pSlope"] = data.slope

    depths = data.depth_dependent_data

    for depth in depths:
        inputs["topDepth"].append(depth.depth_interval.start)
        inputs["bottomDepth"].append(depth.depth_interval.end)

        inputs["soilHorizon"].append(parse_texture(depth.texture))
        inputs["rfvDepth"].append(parse_rock_fragment_volume(depth.rock_fragment_volume))
        inputs["lab_Color"].append(parse_color_LAB(depth.color_LAB))

    return inputs


def resolve_data_based_soil_matches(
    data_region: SoilIdCache.DataRegion, soil_list_json: dict, rank_json: dict
):
    ranked_matches = []
    for ranked_match in rank_json["soilRank"]:
        rankValues = [
            ranked_match["rank_loc"],
            ranked_match["rank_data"],
            ranked_match["rank_data_loc"],
        ]
        if all([value != "Not Displayed" for value in rankValues]):
            ranked_matches.append(
                resolve_data_based_soil_match(data_region, soil_list_json["soilList"], ranked_match)
            )

    return DataBasedSoilMatches(data_region=data_region, matches=ranked_matches)


def resolve_data_based_result(
    _parent, _info, latitude: float, longitude: float, data: Optional[SoilIdInputData] = None
):
    try:
        cached_result = get_cached_list_soils_output(latitude=latitude, longitude=longitude)

        if isinstance(cached_result, str):
            return SoilIdFailure(reason=cached_result)

        data_region, list_output = cached_result

        if data_region == SoilIdCache.DataRegion.US:
            rank_output = us_soil.rank_soils(
                lat=latitude,
                lon=longitude,
                list_output_data=list_output,
                **parse_rank_soils_input_data(data, data_region),
            )
        elif data_region == SoilIdCache.DataRegion.GLOBAL:
            rank_output = global_soil.rank_soils_global(
                lat=latitude,
                lon=longitude,
                list_output_data=list_output,
                connection=soil_id_database_connection(),
                **parse_rank_soils_input_data(data, data_region),
            )
        else:
            raise ValueError(f"Unknown data region: {data_region}")

        return resolve_data_based_soil_matches(
            data_region=data_region,
            soil_list_json=list_output.soil_list_json,
            rank_json=rank_output,
        )
    except Exception:
        logger.error(traceback.format_exc())
        return SoilIdFailure(reason=SoilIdFailureReason.ALGORITHM_FAILURE)
