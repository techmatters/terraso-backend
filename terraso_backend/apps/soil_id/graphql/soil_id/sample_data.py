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

from apps.soil_id.graphql.soil_data import DepthInterval
from apps.soil_id.graphql.soil_id.schema import (
    DataBasedSoilMatch,
    DataBasedSoilMatches,
    EcologicalSite,
    LandCapabilityClass,
    SoilIdDepthDependentData,
    SoilIdSoilData,
    SoilInfo,
    SoilMatchInfo,
    SoilSeries,
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
                ),
                SoilIdDepthDependentData(
                    depth_interval=DepthInterval(start=10, end=15),
                    texture="SILT",
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
            depth_dependent_data=[
                SoilIdDepthDependentData(
                    depth_interval=DepthInterval(start=0, end=10),
                    texture="CLAY_LOAM",
                    rock_fragment_volume="VOLUME_1_15",
                    munsell_color_string="10R 5/4",
                ),
                SoilIdDepthDependentData(
                    depth_interval=DepthInterval(start=10, end=15),
                    rock_fragment_volume="VOLUME_15_35",
                    munsell_color_string="N 4/",
                ),
            ],
        ),
    ),
]

dummy_data_matches = DataBasedSoilMatches(
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
