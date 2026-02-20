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

from apps.soil_id.models.project_soil_settings import (
    BLMIntervalDefaults,
    DepthIntervalPreset,
    NRCSIntervalDefaults,
)


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

# Preset name constants (from DepthIntervalPreset enum)
PRESET_NRCS = DepthIntervalPreset.NRCS.value
PRESET_BLM = DepthIntervalPreset.BLM.value
PRESET_CUSTOM = DepthIntervalPreset.CUSTOM.value
PRESET_NONE = DepthIntervalPreset.NONE.value


def depth_key(interval):
    """Extract (start, end) tuple from an interval dict for matching."""
    di = interval.get("depthInterval", {})
    return (di.get("start"), di.get("end"))


def get_effective_preset(site):
    """
    Determine the effective depth interval preset for a site.

    Priority: project.soilSettings.depthIntervalPreset > site.soilData.depthIntervalPreset

    Returns:
        str: "NRCS", "BLM", "CUSTOM" (project only), or "NONE" (no preset)

    Note: CUSTOM at site level returns "NONE" because it means "no standard preset" -
    custom intervals are added separately.
    CUSTOM at project level returns "CUSTOM" because project defines the intervals.
    """
    project = site.get("project")
    if project:
        return (project.get("soilSettings") or {}).get("depthIntervalPreset") or PRESET_NONE

    # Fall back to site-level preset (only if no project)
    # Site CUSTOM means "no preset" - custom intervals added separately
    soil_data = site.get("soilData", {})
    preset = soil_data.get("depthIntervalPreset")
    return PRESET_NONE if preset == PRESET_CUSTOM else (preset or PRESET_NONE)


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
    for interval in preset_intervals:
        result.append((interval, effective_preset))

    # Add site custom intervals
    site_intervals = site.get("soilData", {}).get("depthIntervals", [])
    for site_interval in site_intervals:
        result.append((site_interval, PRESET_CUSTOM))

    # Sort by start depth
    result.sort(key=lambda x: depth_key(x[0])[0] or 0)
    return result
