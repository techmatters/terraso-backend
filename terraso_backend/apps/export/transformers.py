# Copyright © 2021-2025 Technology Matters
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

from typing import Optional, Tuple

from .services import fetch_all_notes_for_site

# Depth interval presets
depth_intervals_nrcs_gsp = [
    {
        "label": "0-5 cm",
        "depthInterval": {"start": 0, "end": 5},
        "soilTextureEnabled": True,
        "soilColorEnabled": True,
        "soilStructureEnabled": True,
        "carbonatesEnabled": True,
        "phEnabled": True,
        "soilOrganicCarbonMatterEnabled": True,
        "electricalConductivityEnabled": True,
        "sodiumAdsorptionRatioEnabled": True,
    },
    {
        "label": "5-15 cm",
        "depthInterval": {"start": 5, "end": 15},
        "soilTextureEnabled": True,
        "soilColorEnabled": True,
        "soilStructureEnabled": True,
        "carbonatesEnabled": True,
        "phEnabled": True,
        "soilOrganicCarbonMatterEnabled": True,
        "electricalConductivityEnabled": True,
        "sodiumAdsorptionRatioEnabled": True,
    },
    {
        "label": "15-30 cm",
        "depthInterval": {"start": 15, "end": 30},
        "soilTextureEnabled": True,
        "soilColorEnabled": True,
        "soilStructureEnabled": True,
        "carbonatesEnabled": True,
        "phEnabled": True,
        "soilOrganicCarbonMatterEnabled": True,
        "electricalConductivityEnabled": True,
        "sodiumAdsorptionRatioEnabled": True,
    },
    {
        "label": "30-60 cm",
        "depthInterval": {"start": 30, "end": 60},
        "soilTextureEnabled": False,
        "soilColorEnabled": False,
        "soilStructureEnabled": False,
        "carbonatesEnabled": False,
        "phEnabled": False,
        "soilOrganicCarbonMatterEnabled": False,
        "electricalConductivityEnabled": False,
        "sodiumAdsorptionRatioEnabled": False,
    },
    {
        "label": "60-100 cm",
        "depthInterval": {"start": 60, "end": 100},
        "soilTextureEnabled": False,
        "soilColorEnabled": False,
        "soilStructureEnabled": False,
        "carbonatesEnabled": False,
        "phEnabled": False,
        "soilOrganicCarbonMatterEnabled": False,
        "electricalConductivityEnabled": False,
        "sodiumAdsorptionRatioEnabled": False,
    },
    {
        "label": "100-200 cm",
        "depthInterval": {"start": 100, "end": 200},
        "soilTextureEnabled": False,
        "soilColorEnabled": False,
        "soilStructureEnabled": False,
        "carbonatesEnabled": False,
        "phEnabled": False,
        "soilOrganicCarbonMatterEnabled": False,
        "electricalConductivityEnabled": False,
        "sodiumAdsorptionRatioEnabled": False,
    },
]

depth_intervals_blm = [
    {
        "label": "0-1 cm",
        "depthInterval": {"start": 0, "end": 1},
        "soilTextureEnabled": True,
        "soilColorEnabled": True,
        "soilStructureEnabled": True,
        "carbonatesEnabled": True,
        "phEnabled": True,
        "soilOrganicCarbonMatterEnabled": True,
        "electricalConductivityEnabled": True,
        "sodiumAdsorptionRatioEnabled": True,
    },
    {
        "label": "1-10 cm",
        "depthInterval": {"start": 1, "end": 10},
        "soilTextureEnabled": True,
        "soilColorEnabled": True,
        "soilStructureEnabled": True,
        "carbonatesEnabled": True,
        "phEnabled": True,
        "soilOrganicCarbonMatterEnabled": True,
        "electricalConductivityEnabled": True,
        "sodiumAdsorptionRatioEnabled": True,
    },
    {
        "label": "10-20 cm",
        "depthInterval": {"start": 10, "end": 20},
        "soilTextureEnabled": True,
        "soilColorEnabled": True,
        "soilStructureEnabled": True,
        "carbonatesEnabled": True,
        "phEnabled": True,
        "soilOrganicCarbonMatterEnabled": True,
        "electricalConductivityEnabled": True,
        "sodiumAdsorptionRatioEnabled": True,
    },
    {
        "label": "20-50 cm",
        "depthInterval": {"start": 20, "end": 50},
        "soilTextureEnabled": False,
        "soilColorEnabled": False,
        "soilStructureEnabled": False,
        "carbonatesEnabled": False,
        "phEnabled": False,
        "soilOrganicCarbonMatterEnabled": False,
        "electricalConductivityEnabled": False,
        "sodiumAdsorptionRatioEnabled": False,
    },
    {
        "label": "50-70 cm",
        "depthInterval": {"start": 50, "end": 70},
        "soilTextureEnabled": False,
        "soilColorEnabled": False,
        "soilStructureEnabled": False,
        "carbonatesEnabled": False,
        "phEnabled": False,
        "soilOrganicCarbonMatterEnabled": False,
        "electricalConductivityEnabled": False,
        "sodiumAdsorptionRatioEnabled": False,
    },
]

# String mappings from terraso-mobile-client
rock_fragment_volume = {
    "VOLUME_0_1": "0–1%",
    "VOLUME_1_15": "1–15%",
    "VOLUME_15_35": "15–35%",
    "VOLUME_35_60": "35–60%",
    "VOLUME_60": ">60%",
}

soil_texture = {
    "CLAY": "Clay",
    "CLAY_LOAM": "Clay Loam",
    "LOAM": "Loam",
    "LOAMY_SAND": "Loamy Sand",
    "SAND": "Sand",
    "SANDY_CLAY": "Sandy Clay",
    "SANDY_CLAY_LOAM": "Sandy Clay Loam",
    "SANDY_LOAM": "Sandy Loam",
    "SILT": "Silt",
    "SILTY_CLAY": "Silty Clay",
    "SILTY_CLAY_LOAM": "Silty Clay Loam",
    "SILT_LOAM": "Silt Loam",
}

vertical_cracking = {
    "NO_CRACKING": "No cracks",
    "SURFACE_CRACKING_ONLY": "Surface cracks only",
    "DEEP_VERTICAL_CRACKS": "Deep vertical cracks",
}

# Munsell color conversion constants
non_neutral_color_hues = ["R", "YR", "Y", "GY", "G", "BG", "B", "PB", "P", "RP"]
color_values = [2, 2.5, 3, 4, 5, 6, 7, 8, 8.5, 9, 9.5]


def add_default_depth_intervals(soil_data):
    match soil_data["depthIntervalPreset"]:
        case "NRCS":
            soil_data["depthIntervals"] = depth_intervals_nrcs_gsp
        case "BLM":
            soil_data["depthIntervals"] = depth_intervals_blm


def add_munsell_color_strings(depth_dependent_data):
    for d in depth_dependent_data:
        d["colorMunsell"] = munsell_to_string(d)


def hide_site_id(site):
    site["id"] = "hide id?"


def replace_rock_fragment_volume_strings(depth_dependent_data):
    for d in depth_dependent_data:
        if d.get("rockFragmentVolume"):
            d["rockFragmentVolume"] = rock_fragment_volume.get(
                d.get("rockFragmentVolume"), d.get("rockFragmentVolume")
            )


def replace_soil_texture_strings(depth_dependent_data):
    for d in depth_dependent_data:
        if d.get("texture"):
            d["texture"] = soil_texture.get(d.get("texture"), d.get("texture"))


def replace_surface_cracking_strings(soil_data):
    if soil_data.get("surfaceCracksSelect"):
        soil_data["surfaceCracksSelect"] = vertical_cracking.get(
            soil_data.get("surfaceCracksSelect"), soil_data.get("surfaceCracksSelect")
        )


def render_munsell_hue(color_hue: Optional[float], color_chroma: Optional[float]) -> Tuple[Optional[int], Optional[str]]:
    if color_hue is None:
        return None, None

    if isinstance(color_chroma, (int, float)) and round(color_chroma) == 0:
        return None, "N"

    if color_hue == 100:
        color_hue = 0

    hue_index = int(color_hue // 10)
    substep = round((color_hue % 10) / 2.5)

    if substep == 0:
        hue_index = (hue_index + 9) % 10
        substep = 4

    substep = (substep * 5) / 2

    return substep, non_neutral_color_hues[hue_index]


def munsell_to_string(color: dict) -> str:
    """
    Convert color dictionary to Munsell string representation.
    color = {"colorHue": float, "colorValue": float, "colorChroma": float}
    """
    hue_substep, hue = render_munsell_hue(color.get("colorHue"), color.get("colorChroma"))
    v = color.get("colorValue")
    c = color.get("colorChroma")

    if c is None:
        return "N"

    if v is None:
        v = 0

    # snap value to closest allowed value
    value = min(color_values, key=lambda v_allowed: abs(v_allowed - v))
    chroma = round(c)
    if chroma == 0:
        return f"N {value}/"

    return f"{hue_substep}{hue} {value}/{chroma}"


def flatten_note(note):
    return ",".join([note["content"], note["author"]["email"], note["createdAt"]])


def flatten_site(site: dict) -> dict:
    """Returns n rows of flattened data, one per depth interval"""
    soil_data = site.get("soilData", {})
    notes = site.get("notes")
    rows = []

    flattened_notes = [flatten_note(note) for note in notes] if notes else []

    for depth_interval, depth_dependent_data in zip(
        soil_data.get("depthIntervals", []), soil_data.get("depthDependentData", [])
    ):
        flat = {
            "id": site["id"],
            "name": site["name"],
            "projectName": site["project"]["name"],
            "latitude": site["latitude"],
            "longitude": site["longitude"],
            "elevation": site["elevation"],
            "updatedAt": site["updatedAt"],
            "slopeSteepnessDegree": soil_data.get("slopeSteepnessDegree"),
            "downSlope": soil_data.get("downSlope"),
            "surfaceCracksSelect": soil_data.get("surfaceCracksSelect"),
            "notes": ";".join(flattened_notes),
            "user-selected-soil": site.get("soilMetadata", {}).get("selectedSoilId"),
            # depth interval specific data
            "depth-label": depth_interval.get("label"),
            "depth-start": depth_interval.get("depthInterval").get("start"),
            "depth-end": depth_interval.get("depthInterval").get("end"),
            "depth-rockFragmentVolume": depth_dependent_data.get("rockFragmentVolume"),
            "depth-texture": depth_dependent_data.get("texture"),
            "depth-color": depth_dependent_data.get("colorMunsell"),  # added earlier
        }
        rows.append(flat)

    return rows


def transform_site_data(site, request, page_size=50):
    """Apply all transformations to site data"""
    # reshape the data a bit
    add_default_depth_intervals(site["soilData"])
    add_munsell_color_strings(site["soilData"].get("depthDependentData", []))
    replace_rock_fragment_volume_strings(site["soilData"].get("depthDependentData", []))
    replace_soil_texture_strings(site["soilData"].get("depthDependentData", []))
    replace_surface_cracking_strings(site["soilData"])

    # Add notes
    notes = fetch_all_notes_for_site(site["id"], request, page_size)
    site["notes"] = notes

    # hide_site_id(site)

    return site
