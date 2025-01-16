from apps.soil_id.graphql.soil_id.resolvers import (
    resolve_data_based_soil_match,
    resolve_data_based_soil_matches,
    resolve_ecological_site,
    resolve_land_capability_class,
    resolve_location_based_soil_match,
    resolve_location_based_soil_matches,
    resolve_rock_fragment_volume,
    resolve_soil_data,
    resolve_soil_info,
    resolve_soil_match_info,
    resolve_texture,
)

sample_soil_list_json = [
    {
        "id": {"name": "Randall1", "component": "Randall", "score_loc": 0.9, "rank_loc": "1"},
        "site": {
            "siteData": {
                "mapunitID": "369864",
                "componentID": "24140424",
                "componentKind": "Series",
                "dataSource": "SSURGO",
                "textureInfill": "No",
                "rfvInfill": "No",
                "componentPct": 80,
                "distance": 0.0,
                "minCompDistance": 0.0,
                "slope": 0.5,
                "nirrcapcl": "6",
                "nirrcapscl": "w",
                "nirrcapunit": "None",
                "irrcapcl": "nan",
                "irrcapscl": "None",
                "irrcapunit": "None",
                "taxsubgrp": "Ustic Epiaquerts",
                "sdeURL": "https://casoilresource.lawr.ucdavis.edu/sde/?series=randall",
                "seeURL": "https://casoilresource.lawr.ucdavis.edu/see/#randall",
            },
            "siteDescription": "The Randall series consists of very deep, poorly drained, very slowly permeable soils that formed in clayey lacustrine sediments derived from the Blackwater Draw Formation of Pleistocene age. These nearly level soils are on the floor of playa basins 3 to 15 m (10 to 50 ft) below the surrounding plain and range in size from 10 to more than 150 acres. Slope ranges from 0 to 1 percent. Mean annual precipitation is 483 mm (19 in), and mean annual temperature is 15 degrees C (59 degrees F).",  # noqa: E501
        },
        "esd": {"ESD": {"ecoclassid": "", "ecoclassname": "", "edit_url": ""}},
        "bottom_depth": {"0": 30, "1": 94, "2": 203},
        "texture": {"0": "", "1": "Clay loam", "2": float("nan")},
        "rock_fragments": {"0": 0, "1": "", "2": 0},
        "munsell": {"0": "10YR 4/1", "1": "10YR 5/1", "2": "2.5Y 5/1"},
    },
    {
        "id": {"name": "Acuff1", "component": "Acuff", "score_loc": 0.518, "rank_loc": "2"},
        "site": {
            "siteData": {
                "mapunitID": "369839",
                "componentID": "24140822",
                "componentKind": "Series",
                "dataSource": "SSURGO",
                "textureInfill": "No",
                "rfvInfill": "No",
                "componentPct": 85,
                "distance": 90.0,
                "minCompDistance": 90.0,
                "slope": "",
                "nirrcapcl": "3",
                "nirrcapscl": "e",
                "nirrcapunit": "None",
                "irrcapcl": "3",
                "irrcapscl": "e",
                "irrcapunit": "None",
                "taxsubgrp": "Aridic Paleustolls",
                "sdeURL": "https://casoilresource.lawr.ucdavis.edu/sde/?series=acuff",
                "seeURL": "https://casoilresource.lawr.ucdavis.edu/see/#acuff",
            },
            "siteDescription": "",
        },
        "esd": {"ESD": {"ecoclassid": "", "ecoclassname": "", "edit_url": ""}},
        "bottom_depth": {"0": 30, "1": 97, "2": 147, "3": 203},
        "sand": {"0": 49.1, "1": 48.9, "2": 48.7, "3": 52.5},
        "clay": {"0": 20.2, "1": 27.6, "2": 32.1, "3": 29.8},
        "texture": {
            "0": "Loam",
            "1": "Sandy clay loam",
            "2": "Sandy clay loam",
            "3": "Sandy clay loam",
        },
        "rock_fragments": {"0": 0, "1": 0, "2": 8, "3": 5},
        "cec": {"0": "CEC", "1": "CEC"},
        "ph": {"0": 7.2, "1": 8.2, "2": 8.4, "3": 8.2},
        "ec": {"0": 1.0, "1": 1.0, "2": 1.0, "3": 1.0},
        "lab": {
            "0": [41.26, 8.48, 17.9],
            "1": [48.38, 14.83, 24.62],
            "2": [81.39, 10.73, 20.65],
            "3": [61.74, 17.21, 30.85],
        },
        "munsell": {
            "0": "{color_ref.at[idx, 'hue']} 4/3",
            "1": "{color_ref.at[idx, 'hue']} 5/5",
            "2": "{color_ref.at[idx, 'hue']} 8/4",
            "3": "{color_ref.at[idx, 'hue']} 6/6",
        },
    },
    {
        "id": {
            "name": "Acuff2",
            "component": "Acuff",
            "score_loc": 0.518,
            "rank_loc": "Not Displayed",
        },
        "site": {
            "siteData": {
                "mapunitID": "369851",
                "componentID": "24140753",
                "componentKind": "Series",
                "dataSource": "SSURGO",
                "textureInfill": "No",
                "rfvInfill": "No",
                "componentPct": 5,
                "distance": 204.0,
                "minCompDistance": 90.0,
                "slope": 0.5,
                "nirrcapcl": "None",
                "nirrcapscl": "nan",
                "nirrcapunit": "None",
                "irrcapcl": "2",
                "irrcapscl": "s",
                "irrcapunit": "None",
                "taxsubgrp": "Aridic Paleustolls",
                "sdeURL": "https://casoilresource.lawr.ucdavis.edu/sde/?series=acuff",
                "seeURL": "https://casoilresource.lawr.ucdavis.edu/see/#acuff",
            },
            "siteDescription": "",
        },
        "esd": {"ESD": {"ecoclassid": "", "ecoclassname": "", "edit_url": ""}},
        "bottom_depth": {"0": 30, "1": 97, "2": 147, "3": 203},
        "sand": {"0": 50.9, "1": 48.9, "2": 48.7, "3": 52.5},
        "clay": {"0": 19.1, "1": 27.6, "2": 32.1, "3": 29.8},
        "texture": {
            "0": "Loam",
            "1": "Sandy clay loam",
            "2": "Sandy clay loam",
            "3": "Sandy clay loam",
        },
        "rock_fragments": {"0": 0, "1": 0, "2": 8, "3": 5},
        "cec": {"0": "CEC", "1": "CEC"},
        "ph": {"0": 7.2, "1": 8.2, "2": 8.4, "3": 8.2},
        "ec": {"0": 1.0, "1": 1.0, "2": 1.0, "3": 1.0},
        "lab": {
            "0": [41.26, 8.48, 17.9],
            "1": [48.38, 14.83, 24.62],
            "2": [81.39, 10.73, 20.65],
            "3": [61.74, 17.21, 30.85],
        },
        "munsell": {
            "0": "{color_ref.at[idx, 'hue']} 4/3",
            "1": "{color_ref.at[idx, 'hue']} 5/5",
            "2": "{color_ref.at[idx, 'hue']} 8/4",
            "3": "{color_ref.at[idx, 'hue']} 6/6",
        },
    },
]

sample_rank_json = [
    {
        "name": "Randall",
        "component": "Randall",
        "componentID": 24140424,
        "score_data_loc": 0.21,
        "rank_data_loc": "2",
        "score_data": 0.5,
        "rank_data": "2",
        "score_loc": 1.0,
        "rank_loc": "1",
        "componentData": "Data Complete",
    },
    {
        "name": "Acuff1",
        "component": "Acuff",
        "componentID": 24140822,
        "score_data_loc": 0.29,
        "rank_data_loc": "1",
        "score_data": 0.927,
        "rank_data": "1",
        "score_loc": 0.517,
        "rank_loc": "2",
        "componentData": "Data Complete",
    },
    {
        "name": "Acuff2",
        "component": "Acuff",
        "componentID": 24140753,
        "score_data_loc": 0.211,
        "rank_data_loc": "Not Displayed",
        "score_data": 0.898,
        "rank_data": "Not Displayed",
        "score_loc": 0.517,
        "rank_loc": "Not Displayed",
        "componentData": "Data Complete",
    },
]


def test_resolve_texture():
    assert resolve_texture("Clay loam") == "CLAY_LOAM"
    assert resolve_texture("") is None
    assert resolve_texture(float("nan")) is None


def test_resolve_rock_fragment_volume():
    assert resolve_rock_fragment_volume("") is None
    assert resolve_rock_fragment_volume(0.5) == "VOLUME_0_1"
    assert resolve_rock_fragment_volume(1) == "VOLUME_0_1"
    assert resolve_rock_fragment_volume(15) == "VOLUME_1_15"
    assert resolve_rock_fragment_volume(35) == "VOLUME_15_35"
    assert resolve_rock_fragment_volume(60) == "VOLUME_35_60"
    assert resolve_rock_fragment_volume(60.01) == "VOLUME_60"


def test_resolve_soil_data():
    result = resolve_soil_data(soil_match=sample_soil_list_json[0])

    assert result.slope == 0.5

    assert result.depth_dependent_data[0].depth_interval.start == 0
    assert result.depth_dependent_data[0].depth_interval.end == 30
    assert result.depth_dependent_data[0].munsell_color_string == "10YR 4/1"
    assert result.depth_dependent_data[0].texture is None
    assert result.depth_dependent_data[0].rock_fragment_volume == "VOLUME_0_1"

    assert result.depth_dependent_data[1].depth_interval.start == 30
    assert result.depth_dependent_data[1].depth_interval.end == 94
    assert result.depth_dependent_data[1].munsell_color_string == "10YR 5/1"
    assert result.depth_dependent_data[1].texture == "CLAY_LOAM"
    assert result.depth_dependent_data[1].rock_fragment_volume is None

    assert result.depth_dependent_data[2].depth_interval.start == 94
    assert result.depth_dependent_data[2].depth_interval.end == 203
    assert result.depth_dependent_data[2].munsell_color_string == "2.5Y 5/1"
    assert result.depth_dependent_data[2].texture is None
    assert result.depth_dependent_data[2].rock_fragment_volume == "VOLUME_0_1"


def test_resolve_ecological_site():
    assert resolve_ecological_site({"ecoclassid": "", "ecoclassname": "", "edit_url": ""}) is None
    assert (
        resolve_ecological_site({"ecoclassid": [""], "ecoclassname": [""], "edit_url": [""]})
        is None
    )

    result = resolve_ecological_site(
        {
            "ecoclassid": ["AX001X02X001"],
            "ecoclassname": ["Mesic Udic Riparian Forest"],
            "edit_url": [""],
        }
    )

    assert result.name == "Mesic Udic Riparian Forest"
    assert result.id == "AX001X02X001"
    assert result.url == ""


def test_resolve_land_capability_class_success():
    result = resolve_land_capability_class({"nirrcapcl": "6", "nirrcapscl": "s"})

    assert result.capability_class == "6"
    assert result.sub_class == "s"


def test_resolve_land_capability_class_not_available():
    result = resolve_land_capability_class({"nirrcapcl": "None", "nirrcapscl": "nan"})

    assert result.capability_class == ""
    assert result.sub_class == ""


def test_resolve_soil_info():
    result = resolve_soil_info(sample_soil_list_json[0])

    assert result.soil_series.name == "Randall"
    assert result.soil_series.taxonomy_subgroup == "Ustic Epiaquerts"
    assert (
        result.soil_series.description
        == "The Randall series consists of very deep, poorly drained, very slowly permeable soils that formed in clayey lacustrine sediments derived from the Blackwater Draw Formation of Pleistocene age. These nearly level soils are on the floor of playa basins 3 to 15 m (10 to 50 ft) below the surrounding plain and range in size from 10 to more than 150 acres. Slope ranges from 0 to 1 percent. Mean annual precipitation is 483 mm (19 in), and mean annual temperature is 15 degrees C (59 degrees F)."  # noqa: E501
    )
    assert (
        result.soil_series.full_description_url
        == "https://casoilresource.lawr.ucdavis.edu/sde/?series=randall"
    )

    assert result.land_capability_class.capability_class == "6"
    assert result.land_capability_class.sub_class == "w"


def test_resolve_soil_match_info():
    result = resolve_soil_match_info(0.5, "1")

    assert result.score == 0.5
    assert result.rank == 0


def test_resolve_location_based_soil_match():
    result = resolve_location_based_soil_match(sample_soil_list_json[0])

    assert result.data_source == "SSURGO"
    assert result.distance_to_nearest_map_unit_m == 0.0
    assert result.match.rank == 0
    assert result.soil_info.soil_series.name == "Randall"


def test_resolve_location_based_soil_matches():
    result = resolve_location_based_soil_matches({"soilList": sample_soil_list_json})

    assert len(result.matches) == 2


def test_resolve_data_based_soil_match():
    result = resolve_data_based_soil_match(sample_soil_list_json, sample_rank_json[0])

    assert result.data_source == "SSURGO"
    assert result.distance_to_nearest_map_unit_m == 0.0
    assert result.data_match.rank == 1
    assert result.location_match.rank == 0
    assert result.combined_match.rank == 1
    assert result.soil_info.soil_series.name == "Randall"


def test_resolve_data_based_soil_matches():
    result = resolve_data_based_soil_matches(
        {"soilList": sample_soil_list_json}, {"soilRank": sample_rank_json}
    )

    assert len(result.matches) == 2
