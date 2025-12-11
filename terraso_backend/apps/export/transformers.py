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

from django.conf import settings

from apps.soil_id.models.depth_dependent_soil_data import DepthDependentSoilData
from apps.soil_id.models.project_soil_settings import BLMIntervalDefaults, NRCSIntervalDefaults
from apps.soil_id.models.soil_data import SoilData

from .fetch_data import fetch_all_notes_for_site


def _build_depth_intervals(interval_defaults):
    """
    Convert interval defaults from project_soil_settings format to export format.

    Input format:  {"depth_interval_start": 0, "depth_interval_end": 5}
    Output format: {"label": "0-5 cm", "depthInterval": {"start": 0, "end": 5}}
    """
    return [
        {
            "label": f"{d['depth_interval_start']}-{d['depth_interval_end']} cm",
            "depthInterval": {
                "start": d["depth_interval_start"],
                "end": d["depth_interval_end"],
            },
        }
        for d in interval_defaults
    ]


# Depth interval presets (derived from soil_id source of truth)
NRCS_DEPTH_INTERVALS = _build_depth_intervals(NRCSIntervalDefaults)
BLM_DEPTH_INTERVALS = _build_depth_intervals(BLMIntervalDefaults)


# Helper functions for converting enum codes to human-readable labels


def code_to_label(code_value, capitalize_all_words=True):
    """
    Convert a database code like "SILTY_CLAY" to a human-readable label like "Silty Clay".

    Args:
        code_value: The code string (e.g., "SILTY_CLAY", "NO_CRACKING")
        capitalize_all_words: If True, capitalize all words. If False, only capitalize first word.

    Returns:
        Human-readable label string

    Examples:
        code_to_label("SILTY_CLAY") -> "Silty Clay"
        code_to_label("NO_CRACKING") -> "No Cracking"
        code_to_label("DEEP_VERTICAL_CRACKS") -> "Deep Vertical Cracks"
        code_to_label("SILTY_CLAY", capitalize_all_words=False) -> "Silty clay"
    """
    if not code_value:
        return code_value

    # Replace underscores with spaces
    words = code_value.split("_")

    if capitalize_all_words:
        # Capitalize each word: "SILTY_CLAY" -> "Silty Clay"
        return " ".join(word.capitalize() for word in words)
    else:
        # Only capitalize first word: "SILTY_CLAY" -> "Silty clay"
        return " ".join(
            word.capitalize() if i == 0 else word.lower() for i, word in enumerate(words)
        )


def get_enum_label(enum_class, value, fallback=None):
    """
    Get the human-readable label for a Django TextChoices enum value.

    Uses Django's built-in label system, which automatically generates labels
    from enum values (e.g., "SILTY_CLAY" -> "Silty Clay") or uses custom labels
    if defined in the enum.

    Args:
        enum_class: The Django TextChoices class (e.g., DepthDependentSoilData.Texture)
        value: The enum value (e.g., "SILTY_CLAY")
        fallback: Optional fallback function if value not in enum (default: code_to_label)

    Returns:
        The label string, or the result of fallback function if value not found

    Examples:
        get_enum_label(DepthDependentSoilData.Texture, "SILTY_CLAY") -> "Silty Clay"
        get_enum_label(DepthDependentSoilData.RockFragmentVolume, "VOLUME_0_1") -> "0 — 1%"
    """
    try:
        return enum_class(value).label
    except (ValueError, KeyError):
        # Value not in enum - use fallback if provided
        if fallback:
            return fallback(value)
        # Default fallback: use code_to_label helper
        return code_to_label(value)


# Munsell color conversion constants
non_neutral_color_hues = ["R", "YR", "Y", "GY", "G", "BG", "B", "PB", "P", "RP"]
color_values = [2, 2.5, 3, 4, 5, 6, 7, 8, 8.5, 9, 9.5]

# Configuration: Maps field names to their Django enum classes
# This drives automatic label generation for all simple enum fields
SIMPLE_ENUM_MAPPINGS = {
    # SoilData enums
    "downSlope": SoilData.SlopeShape,
    "crossSlope": SoilData.SlopeShape,
    "slopeLandscapePosition": SoilData.LandscapePosition,
    "slopeSteepnessSelect": SoilData.SlopeSteepness,
    "surfaceCracksSelect": SoilData.SurfaceCracks,
    "surfaceSaltSelect": SoilData.SurfaceSalt,
    "floodingSelect": SoilData.Flooding,
    "limeRequirementsSelect": SoilData.LimeRequirements,
    "surfaceStoninessSelect": SoilData.SurfaceStoniness,
    "waterTableDepthSelect": SoilData.WaterTableDepth,
    "soilDepthSelect": SoilData.SoilDepth,
    "landCoverSelect": SoilData.LandCover,
    "grazingSelect": SoilData.Grazing,
    # DepthDependentSoilData enums
    "texture": DepthDependentSoilData.Texture,
    "rockFragmentVolume": DepthDependentSoilData.RockFragmentVolume,
    "colorPhotoSoilCondition": DepthDependentSoilData.ColorPhotoSoilCondition,
    "colorPhotoLightingCondition": DepthDependentSoilData.ColorPhotoLightingCondition,
    "conductivityTest": DepthDependentSoilData.ConductivityTest,
    "conductivityUnit": DepthDependentSoilData.ConductivityUnit,
    "structure": DepthDependentSoilData.SoilStructure,
    "phTestingSolution": DepthDependentSoilData.PhTestingSolution,
    "phTestingMethod": DepthDependentSoilData.PhTestingMethod,
}


# Object-level transformer functions
# Each transformer receives a dict and adds manufactured fields as needed


def add_simple_enum_labels(obj):
    """
    Replace enum code values with human-readable labels in-place.

    Iterates through SIMPLE_ENUM_MAPPINGS and replaces enum code values
    (e.g., "SILTY_CLAY") with their human-readable labels (e.g., "Silty Clay").

    This single function replaces ~20 individual transformer functions,
    making it easy to add new enum fields by just updating SIMPLE_ENUM_MAPPINGS.
    """
    for field_name, enum_class in SIMPLE_ENUM_MAPPINGS.items():
        if field_name in obj and obj[field_name] is not None:
            obj[field_name] = get_enum_label(enum_class, obj[field_name])


def add_munsell_color_label(obj):
    """
    Add _colorMunsell label if any color fields exist.

    Special case: This derives from 3 separate fields (colorHue, colorValue, colorChroma)
    rather than transforming a single enum field, so it can't use the simple mapping approach.
    """
    if any(k in obj for k in ["colorHue", "colorValue", "colorChroma"]):
        obj["_colorMunsell"] = munsell_to_string(obj)


def format_rock_fragment_volume(obj):
    """
    Format rockFragmentVolume to use regular dash without spaces.

    Converts "0 — 1%" to "0-1%" and "1 — 15%" to "1-15%", etc.
    This formatting is applied after enum label transformation.
    """
    if "rockFragmentVolume" in obj and obj["rockFragmentVolume"] is not None:
        # Replace em-dash with regular dash and remove all spaces
        value = obj["rockFragmentVolume"]
        value = value.replace("—", "-")  # Replace em-dash with regular dash
        value = value.replace(" ", "")  # Remove all spaces
        obj["rockFragmentVolume"] = value


def format_slope_steepness(obj):
    """
    Format slopeSteepnessSelect to use dash without spaces around it.

    Converts "0 - 2% (flat)" to "0-2% (flat)", preserving space before parentheses.
    This formatting is applied after enum label transformation.
    """
    if "slopeSteepnessSelect" in obj and obj["slopeSteepnessSelect"] is not None:
        # Replace " - " with "-" to remove spaces around dash
        value = obj["slopeSteepnessSelect"]
        value = value.replace(" - ", "-")
        obj["slopeSteepnessSelect"] = value


# Registry of object-level transformers
OBJECT_TRANSFORMERS = [
    add_simple_enum_labels,  # Handles all simple enum fields via SIMPLE_ENUM_MAPPINGS
    format_rock_fragment_volume,  # Format rock fragment volume after enum transformation
    format_slope_steepness,  # Format slope steepness after enum transformation
    add_munsell_color_label,  # Special case: multi-field transformation
]


def apply_object_transformations(data):
    """
    Recursively walk data structure and apply object-level transformations.

    For each dict encountered, runs all registered transformers.
    Each transformer can inspect the dict and add manufactured fields as needed.

    Args:
        data: dict, list, or primitive value to transform

    Returns:
        The data structure with manufactured fields added (mutates in place)
    """
    if isinstance(data, dict):
        # Apply all transformers to this object
        for transformer in OBJECT_TRANSFORMERS:
            transformer(data)

        # Recursively process nested structures
        for value in data.values():
            apply_object_transformations(value)

    elif isinstance(data, list):
        # Process each item in the list
        for item in data:
            apply_object_transformations(item)

    return data


def add_default_depth_intervals(soil_data):
    """
    Add default depth intervals based on preset, only if depthIntervals don't already exist.
    Custom depth intervals (if present) will be preserved.
    """
    # Only add defaults if no custom intervals exist
    if "depthIntervals" not in soil_data or not soil_data["depthIntervals"]:
        match soil_data.get("depthIntervalPreset"):
            case "NRCS":
                soil_data["depthIntervals"] = NRCS_DEPTH_INTERVALS
            case "BLM":
                soil_data["depthIntervals"] = BLM_DEPTH_INTERVALS
            case _:
                # Unknown preset or no preset - leave depthIntervals as-is
                # (might be custom intervals or empty)
                pass


def merge_depth_intervals_into_data(soil_data):
    """
    Merge depthIntervals and depthDependentData into single depthDependentData array.

    Each item in the resulting depthDependentData will have:
    - Depth interval metadata (label, depthIntervalStart, depthIntervalEnd, *Enabled flags)
    - Measurement data (texture, color, etc. - may be null)

    This ensures we always have all depth intervals in the export, even if some
    have no measurements.

    The number of intervals varies:
    - NRCS preset: 6 intervals (0-5, 5-15, 15-30, 30-60, 60-100, 100-200 cm)
    - BLM preset: 5 intervals (0-1, 1-10, 10-20, 20-50, 50-70 cm)
    - Custom intervals: Any number defined by the user
    """
    depth_intervals = soil_data.get("depthIntervals", [])
    depth_dependent_data = soil_data.get("depthDependentData", [])

    # Create a merged list
    merged_data = []

    for i, interval in enumerate(depth_intervals):
        # Start with interval metadata (make a copy to avoid mutating presets)
        merged_item = interval.copy()

        # Flatten depthInterval structure to depthIntervalStart and depthIntervalEnd
        if "depthInterval" in merged_item:
            depth_interval = merged_item.pop("depthInterval")
            merged_item["depthIntervalStart"] = depth_interval.get("start")
            merged_item["depthIntervalEnd"] = depth_interval.get("end")

        # Add measurement data if it exists for this index
        if i < len(depth_dependent_data):
            measurement_data = depth_dependent_data[i]
            merged_item.update(measurement_data)

        merged_data.append(merged_item)

    # Replace both arrays with single merged array
    soil_data["depthDependentData"] = merged_data
    # Remove old depthIntervals array
    if "depthIntervals" in soil_data:
        del soil_data["depthIntervals"]


def render_munsell_hue(
    color_hue: Optional[float], color_chroma: Optional[float]
) -> Tuple[Optional[float], Optional[str]]:
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
    # Format timestamp for better readability (will be further processed in CSV formatter)
    return " | ".join([note["content"], note["author"]["email"], note["createdAt"]])


def flatten_site(site: dict) -> dict:
    # Returns n rows of flattened data, one per depth interval

    soil_data = site.get("soilData", {})
    notes = site.get("notes")
    rows = []

    flattened_notes = [flatten_note(note) for note in notes] if notes else []

    # Get merged depth data (now contains both interval metadata and measurements)
    depth_dependent_data = soil_data.get("depthDependentData", [])

    # Ensure at least one row even if no depth data
    if not depth_dependent_data:
        depth_dependent_data = [None]

    user_selected_soil = site.get("soilMetadata", {}).get("selectedSoilId")

    # Extract soil ID match data
    soil_id_data = site.get("soil_id", {})
    soil_matches = soil_id_data.get("soilId", {}).get("soilMatches", {})

    # Initialize soil data variables
    matching_soil_info = None
    selected_soil_taxonomy = None
    selected_soil_description = None
    lcc_class = None
    ecological_site_name = None
    ecological_site_id = None
    top_match_soil_series = None
    top_match_taxonomy = None
    top_match_description = None

    # Get top match (first in list) regardless of user selection
    if isinstance(soil_matches, dict) and "matches" in soil_matches and soil_matches["matches"]:
        top_match = soil_matches["matches"][0]
        top_match_info = top_match.get("soilInfo", {})
        top_match_series = top_match_info.get("soilSeries", {})
        top_match_soil_series = top_match_series.get("name")
        top_match_taxonomy = top_match_series.get("taxonomySubgroup")
        top_match_description = top_match_series.get("description")

    # Find matching soil info if user selected a soil
    if user_selected_soil and isinstance(soil_matches, dict) and "matches" in soil_matches:
        for match in soil_matches["matches"]:
            soil_series_name = match.get("soilInfo", {}).get("soilSeries", {}).get("name")
            if soil_series_name == user_selected_soil:
                matching_soil_info = match.get("soilInfo")

                # Get selected soil details
                selected_series = matching_soil_info.get("soilSeries", {})
                selected_soil_taxonomy = selected_series.get("taxonomySubgroup")
                selected_soil_description = selected_series.get("description")

                # Get land capability class
                lcc_info = matching_soil_info.get("landCapabilityClass")
                if lcc_info:
                    lcc_class = lcc_info.get("capabilityClass", "") + lcc_info.get("subClass", "")

                # Get ecological site info
                ecological_site_info = matching_soil_info.get("ecologicalSite")
                if ecological_site_info:
                    ecological_site_name = ecological_site_info.get("name")
                    ecological_site_id = ecological_site_info.get("id")
                break

    for depth_item in depth_dependent_data:
        flat = {
            # Site information
            "Site ID": site["id"],
            "Site name": site["name"],
            "Site privacy": site.get("privacy"),
            # Project information
            "Project name": site["project"]["name"] if site["project"] else None,
            "Project ID": site["project"]["id"] if site["project"] else None,
            "Project description": site["project"]["description"] if site["project"] else None,
            # Location and metadata
            "Latitude": site["latitude"],
            "Longitude": site["longitude"],
            "Elevation": site["elevation"],
            "Last updated (UTC)": site["updatedAt"],
            # Soil match information (from soil_id API)
            "Soil map": soil_id_data.get("soilId", {}).get("soilMatches", {}).get("dataRegion"),
            # Selected soil (user's choice)
            "Selected soil series": user_selected_soil,
            "Selected soil type taxonomy subgroup": selected_soil_taxonomy,
            "Selected soil description": selected_soil_description,
            # Top match (best algorithmic match)
            "Top soil series match": top_match_soil_series,
            "Top soil match taxonomy subgroup": top_match_taxonomy,
            "Top soil match description": top_match_description,
            # Ecological and classification
            "Ecological site name": ecological_site_name,
            "Ecological site ID": ecological_site_id,
            "Land capability classification": lcc_class,
            # Slope and surface characteristics
            "Slope steepness degree": soil_data.get("slopeSteepnessDegree"),
            "Down slope": soil_data.get("downSlope"),
            "Cross slope": soil_data.get("crossSlope"),
            "Surface cracks": soil_data.get("surfaceCracksSelect"),
            # Notes
            "Site notes": ";".join(flattened_notes),
            # Depth information
            "Depth preset": soil_data.get("depthIntervalPreset"),
            "Depth label": depth_item.get("label") if depth_item else None,
            "Depth start": depth_item.get("depthIntervalStart") if depth_item else None,
            "Depth end": depth_item.get("depthIntervalEnd") if depth_item else None,
            "Depth rock fragment volume": depth_item.get("rockFragmentVolume")
            if depth_item
            else None,
            "Depth texture class": depth_item.get("texture") if depth_item else None,
            "Depth soil color": depth_item.get("_colorMunsell") if depth_item else None,
            # Color photo metadata
            "Soil color photo used": depth_item.get("colorPhotoUsed") if depth_item else None,
            "Soil color condition": depth_item.get("colorPhotoSoilCondition")
            if depth_item
            else None,
            "Soil color lighting": depth_item.get("colorPhotoLightingCondition")
            if depth_item
            else None,
        }
        rows.append(flat)

    return rows


def transform_site_data(site, request, page_size=settings.EXPORT_PAGE_SIZE):
    """Apply all transformations to site data"""
    # Add default depth intervals
    add_default_depth_intervals(site["soilData"])

    # Merge depth intervals into depth dependent data
    merge_depth_intervals_into_data(site["soilData"])

    # Add notes
    notes = fetch_all_notes_for_site(site["id"], request, page_size)
    site["notes"] = notes

    # Apply all object transformations recursively to entire site
    apply_object_transformations(site)

    return site
