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

import math
import re
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

# Preset name constants
PRESET_NRCS = "NRCS"
PRESET_BLM = "BLM"
PRESET_CUSTOM = "CUSTOM"
PRESET_NONE = "NONE"


# =============================================================================
# Depth interval helpers
# =============================================================================


def depth_key(interval):
    """Extract (start, end) tuple from an interval dict for matching."""
    di = interval.get("depthInterval", {})
    return (di.get("start"), di.get("end"))


def depth_key_flat(item):
    """Extract (start, end) tuple from a flattened item."""
    return (item.get("depthIntervalStart"), item.get("depthIntervalEnd"))


def intervals_overlap(a, b):
    """Check if two intervals overlap (share any depth range)."""
    a_start, a_end = depth_key(a)
    b_start, b_end = depth_key(b)
    if None in (a_start, a_end, b_start, b_end):
        return False
    return a_start < b_end and b_start < a_end


def get_effective_preset(site):
    """
    Determine the effective depth interval preset for a site.

    Priority: project.soilSettings.depthIntervalPreset > site.soilData.depthIntervalPreset

    Note: Site-level CUSTOM is treated as None because "custom" at site level
    means "no standard preset" - custom intervals are added separately.

    Returns:
        str: The effective preset (NRCS, BLM, CUSTOM, NONE) or None
    """
    project = site.get("project")
    if project:
        return (project.get("soilSettings") or {}).get("depthIntervalPreset")

    # Fall back to site-level preset (only if no project)
    # Site CUSTOM means "no preset" - custom intervals added separately
    soil_data = site.get("soilData", {})
    preset = soil_data.get("depthIntervalPreset")
    return None if preset == PRESET_CUSTOM else preset


def get_preset_intervals(preset, site=None):
    """
    Get the standard intervals for a preset.

    For CUSTOM preset, returns project's custom intervals (requires site param).

    Returns list of intervals in format:
    [{"label": "0-5 cm", "depthInterval": {"start": 0, "end": 5}}, ...]
    """
    if preset == PRESET_NRCS:
        return NRCS_DEPTH_INTERVALS
    elif preset == PRESET_BLM:
        return BLM_DEPTH_INTERVALS
    elif preset == PRESET_CUSTOM and site:
        # CUSTOM preset only comes from project (site CUSTOM returns None from get_effective_preset)
        project = site.get("project")
        return (project.get("soilSettings") or {}).get("depthIntervals", [])
    return []


def get_visible_intervals(site):
    """
    Get all visible depth intervals for a site.

    Combines:
    1. Preset intervals (from NRCS, BLM, or project CUSTOM)
    2. Site's custom intervals that don't overlap with #1

    Returns list of (interval, preset_name) tuples.
    """
    effective_preset = get_effective_preset(site)
    result = []

    # Get preset intervals (NRCS, BLM, or project CUSTOM)
    preset_intervals = get_preset_intervals(effective_preset, site)
    preset_label = effective_preset or PRESET_CUSTOM
    for interval in preset_intervals:
        result.append((interval, preset_label))

    # Add non-overlapping site custom intervals
    site_intervals = site.get("soilData", {}).get("depthIntervals", [])
    for site_interval in site_intervals:
        if not any(intervals_overlap(site_interval, p) for p, _ in result):
            result.append((site_interval, PRESET_CUSTOM))

    # Sort by start depth
    result.sort(key=lambda x: depth_key(x[0])[0] or 0)
    return result


def measurement_matches_preset(measurement, preset, custom_intervals):
    """
    Check if a measurement matches an interval in the given preset.

    Returns the preset name if it matches, or empty string if not.
    """
    m_key = depth_key(measurement)

    if preset == PRESET_NRCS:
        if any(depth_key(i) == m_key for i in NRCS_DEPTH_INTERVALS):
            return PRESET_NRCS
    elif preset == PRESET_BLM:
        if any(depth_key(i) == m_key for i in BLM_DEPTH_INTERVALS):
            return PRESET_BLM
    elif preset == PRESET_CUSTOM:
        if any(depth_key(i) == m_key for i in custom_intervals):
            return PRESET_CUSTOM
    elif preset == PRESET_NONE:
        # NONE means all measurements are "custom"
        return PRESET_CUSTOM

    # Also check site custom intervals (non-overlapping with preset)
    if any(depth_key(i) == m_key for i in custom_intervals):
        return PRESET_CUSTOM

    return ""


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
    Add _colorMunsell label if any color fields have values.

    Special case: This derives from 3 separate fields (colorHue, colorValue, colorChroma)
    rather than transforming a single enum field, so it can't use the simple mapping approach.

    Only adds _colorMunsell when at least one color field has a non-null value.
    """
    color_fields = ["colorHue", "colorValue", "colorChroma"]
    if any(obj.get(k) is not None for k in color_fields):
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


def calculate_slope_percentage_range(obj):
    """
    Calculate slope steepness percentage range from whichever input exists.

    Priority: slopeSteepnessPercent > slopeSteepnessDegree > slopeSteepnessSelect

    Sets _slopeSteepnessPercentLow and _slopeSteepnessPercentHigh.
    For exact values (percent/degree), low == high.
    For select categories, uses the range (e.g., FLAT = 0-2%).
    """
    percent = obj.get("slopeSteepnessPercent")
    degree = obj.get("slopeSteepnessDegree")
    select = obj.get("slopeSteepnessSelect")

    low = None
    high = None

    if percent is not None:
        # Exact percent value
        low = high = float(percent)
    elif degree is not None:
        # Convert degree to percent: percent = tan(degrees) * 100
        percent_value = round(math.tan(math.radians(degree)) * 100, 1)
        low = high = percent_value
    elif select is not None:
        # Parse range from display label like "0-2% (flat)" or "100%+ (steepest)"
        # Match "start - end%" or "start-end%"
        range_match = re.search(r"(\d+)\s*-\s*(\d+)%", select)
        if range_match:
            low = int(range_match.group(1))
            high = int(range_match.group(2))
        else:
            # Match "100%+" pattern (no upper bound)
            plus_match = re.search(r"(\d+)%\+", select)
            if plus_match:
                low = int(plus_match.group(1))
                high = 999  # Max app allows

    if low is not None:
        obj["_slopeSteepnessPercentLow"] = low
        obj["_slopeSteepnessPercentHigh"] = high


# Registry of object-level transformers
OBJECT_TRANSFORMERS = [
    add_simple_enum_labels,  # Handles all simple enum fields via SIMPLE_ENUM_MAPPINGS
    format_rock_fragment_volume,  # Format rock fragment volume after enum transformation
    format_slope_steepness,  # Format slope steepness after enum transformation
    calculate_slope_percentage_range,  # Calculate percent range from any slope input
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


def process_depth_data_for_json(site):
    """
    Process depth data for JSON export.

    For JSON, we include ALL measurements with a _depthPreset field indicating
    which protocol they match (NRCS, BLM, CUSTOM, or "" for orphaned).

    Also adds _effectivePreset at the site level.
    """
    soil_data = site.get("soilData", {})
    measurements = soil_data.get("depthDependentData", [])

    effective_preset = get_effective_preset(site)

    # Get preset intervals (project CUSTOM intervals if applicable)
    preset_intervals = get_preset_intervals(effective_preset, site)

    # Combine preset intervals with non-overlapping site intervals for matching
    site_intervals = soil_data.get("depthIntervals", [])
    all_custom = preset_intervals + [
        i for i in site_intervals if not any(depth_key(i) == depth_key(c) for c in preset_intervals)
    ]

    # Index all intervals by (start, end) for metadata lookup
    interval_by_key = {}
    for interval in preset_intervals:
        interval_by_key[depth_key(interval)] = interval
    # Site intervals may override preset intervals with same key
    for interval in site_intervals:
        interval_by_key[depth_key(interval)] = interval

    # Process each measurement: flatten, add metadata, and add _depthPreset
    processed = []
    for m in measurements:
        item = m.copy()

        # Flatten depthInterval to depthIntervalStart/End
        di = item.pop("depthInterval", {})
        start = di.get("start")
        end = di.get("end")
        item["depthIntervalStart"] = start
        item["depthIntervalEnd"] = end

        # Look up interval metadata by (start, end)
        key = (start, end)
        matching_interval = interval_by_key.get(key, {})

        # Use custom label if available, otherwise generate from depth range
        if matching_interval.get("label"):
            item["label"] = matching_interval["label"]
        elif start is not None and end is not None:
            item["label"] = f"{start}-{end} cm"

        # Include enabled flags from matching interval
        for field in ("soilTextureEnabled", "soilColorEnabled"):
            if field in matching_interval:
                item[field] = matching_interval[field]

        # Determine which preset this measurement matches
        item["_depthPreset"] = measurement_matches_preset(m, effective_preset, all_custom)

        processed.append(item)

    # Sort by start depth
    processed.sort(key=lambda x: (x.get("depthIntervalStart") or 0))

    soil_data["depthDependentData"] = processed
    soil_data["_effectivePreset"] = effective_preset

    # Remove depthIntervals from JSON output (not needed)
    soil_data.pop("depthIntervals", None)
    soil_data.pop("depthIntervalPreset", None)


def process_depth_data_for_csv(site):
    """
    Process depth data for CSV export.

    For CSV, we include ALL visible intervals (from preset + non-overlapping custom),
    with matching measurement data merged by (start, end).
    """
    soil_data = site.get("soilData", {})
    measurements = soil_data.get("depthDependentData", [])

    # Index measurements by (start, end) for O(1) lookup
    measurement_by_key = {}
    for m in measurements:
        key = depth_key(m)
        measurement_by_key[key] = m

    # Get all visible intervals
    visible_intervals = get_visible_intervals(site)

    # Build merged data: each interval with its matching measurement (if any)
    merged = []
    for interval, preset_name in visible_intervals:
        item = interval.copy()

        # Flatten depthInterval
        di = item.pop("depthInterval", {})
        item["depthIntervalStart"] = di.get("start")
        item["depthIntervalEnd"] = di.get("end")

        # Generate label if not present
        start, end = item["depthIntervalStart"], item["depthIntervalEnd"]
        if "label" not in item and start is not None and end is not None:
            item["label"] = f"{start}-{end} cm"

        # Add preset marker
        item["_depthPreset"] = preset_name

        # Find and merge matching measurement
        key = (start, end)
        if key in measurement_by_key:
            measurement = measurement_by_key[key].copy()
            measurement.pop("depthInterval", None)
            item.update(measurement)

        merged.append(item)

    soil_data["depthDependentData"] = merged
    soil_data["_effectivePreset"] = get_effective_preset(site)

    # Remove depthIntervals from output
    soil_data.pop("depthIntervals", None)
    soil_data.pop("depthIntervalPreset", None)


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
    author = note.get("author")
    author_email = (author.get("email") if author else None) or "[Pinned Note]"
    created_at = note.get("createdAt") or ""
    return " | ".join([note["content"], author_email, created_at])


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

    # Extract soil ID match data
    soil_id_data = site.get("soil_id", {})
    soil_matches = soil_id_data.get("soilId", {}).get("soilMatches", {})

    # Find user selected soil - look for match with userRating == "SELECTED"
    # (userRating is injected into matches from soilMetadata.userRatings)
    # Fallback to _selectedSoilName if no matches exist (e.g., when soil ID API fails)
    user_selected_soil = None
    if isinstance(soil_matches, dict) and "matches" in soil_matches:
        for match in soil_matches.get("matches", []):
            if match.get("userRating") == "SELECTED":
                user_selected_soil = match.get("soilInfo", {}).get("soilSeries", {}).get("name")
                break
    # Fallback to _selectedSoilName when no matches exist
    if user_selected_soil is None:
        user_selected_soil = site.get("_selectedSoilName")

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
    top_match_user_rating = None
    top_match_data_source = None

    # Get top match (first in list) regardless of user selection
    if isinstance(soil_matches, dict) and "matches" in soil_matches and soil_matches["matches"]:
        top_match = soil_matches["matches"][0]
        top_match_info = top_match.get("soilInfo", {})
        top_match_series = top_match_info.get("soilSeries", {})
        top_match_soil_series = top_match_series.get("name")
        top_match_taxonomy = top_match_series.get("taxonomySubgroup")
        top_match_description = top_match_series.get("description")
        top_match_user_rating = top_match.get("userRating")
        top_match_data_source = top_match.get("dataSource")

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
            # "Last updated (UTC)": site["updatedAt"], // removed because value misleading as it only includes site object itself, not related data
            # Soil match information (from soil_id API)
            "Soil map": top_match_data_source,
            # Selected soil (user's choice)
            "Selected soil series": user_selected_soil,
            "Selected soil type taxonomy subgroup": selected_soil_taxonomy,
            "Selected soil description": selected_soil_description,
            # Top match (best algorithmic match)
            "Top soil series match": top_match_soil_series,
            "Top soil match taxonomy subgroup": top_match_taxonomy,
            "Top soil match description": top_match_description,
            # Default to "Unsure" if there's a top match but no explicit rating
            "Top match user rating": (top_match_user_rating or "Unsure")
            if top_match_soil_series
            else None,
            # Ecological and classification
            "Ecological site name": ecological_site_name,
            "Ecological site ID": ecological_site_id,
            "Land capability classification": lcc_class,
            # Slope and surface characteristics
            "Slope steepness percent low": soil_data.get("_slopeSteepnessPercentLow"),
            "Slope steepness percent high": soil_data.get("_slopeSteepnessPercentHigh"),
            "Down slope": soil_data.get("downSlope"),
            "Cross slope": soil_data.get("crossSlope"),
            "Surface cracks": soil_data.get("surfaceCracksSelect"),
            # Notes
            "Site notes": ";".join(flattened_notes),
            # Depth information
            "Depth preset": depth_item.get("_depthPreset") if depth_item else None,
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


def transform_site_data(site, request, output_format="json", page_size=settings.EXPORT_PAGE_SIZE):
    """
    Apply all transformations to site data.

    Args:
        site: Site data dict from GraphQL
        request: Django request object
        output_format: "json" or "csv" - determines depth processing strategy
        page_size: Page size for notes pagination
    """
    # Process depth data based on output format
    # JSON: include ALL measurements with _depthPreset field
    # CSV: include ALL visible intervals with matching measurements
    if output_format == "csv":
        process_depth_data_for_csv(site)
    else:
        process_depth_data_for_json(site)

    # Add notes
    notes = fetch_all_notes_for_site(site["id"], request, page_size)

    # Prepend project's pinned note (siteInstructions) as first note if it exists
    project = site.get("project")
    if project and project.get("siteInstructions"):
        pinned_note = {
            "content": project["siteInstructions"],
            "createdAt": project.get("updatedAt"),
        }
        notes.insert(0, pinned_note)

    site["notes"] = notes

    # Apply all object transformations recursively to entire site
    apply_object_transformations(site)

    return site
