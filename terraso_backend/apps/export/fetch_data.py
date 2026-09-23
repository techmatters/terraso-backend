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
import threading

import structlog
from django.conf import settings

from apps.graphql.schema.schema import schema

from .depth_helpers import depth_key, get_visible_intervals

logger = structlog.get_logger(__name__)

# Lock protecting the module-level caches below against concurrent access
# from multiple gthread worker threads.
_cache_lock = threading.Lock()

# In-memory cache for soil_id data, only populated during tests (via cache_soil_id
# in fixture_loader.py) to avoid external API calls. Never written to in production.
_soil_id_cache = {}

# Set to False to disable cache (for development/testing without cache)
_USE_SOIL_ID_CACHE = True


# Midpoint (%) of each qualitative slope class, matching the ranges in
# SoilData.SlopeSteepness. For a categorical slope the app/export must pick one
# representative percent; the midpoint is on average closer to the true slope than
# the low edge, which systematically understates it (by up to half a class width
# for wide classes like HILLY 15-30 or STEEP 30-50). Tuning against the US bulk
# test estimated ~+0.5 pt top-1 vs the low edge, recovering the measured-slope
# ceiling. STEEPEST is open-ended, so it stays at its low edge (100).
# NOTE: the mobile client applies the same category->percent mapping independently;
# keep it in sync (update to midpoints there too) or export and app scores diverge.
_SLOPE_SELECT_MIDPOINT_PCT = {
    "FLAT": 1.0,  # 0-2%
    "GENTLE": 3.5,  # 2-5%
    "MODERATE": 7.5,  # 5-10%
    "ROLLING": 12.5,  # 10-15%
    "HILLY": 22.5,  # 15-30%
    "STEEP": 40.0,  # 30-50%
    "MODERATELY_STEEP": 55.0,  # 50-60%
    "VERY_STEEP": 80.0,  # 60-100%
    "STEEPEST": 100.0,  # 100%+ (open-ended; low edge)
}


def _slope_percent(soil_data):
    """Single numeric slope (percent) for the soil-ID query, mirroring the app.

    Priority: explicit percent > degree (converted) > qualitative select midpoint.
    Returns None when no slope was recorded. Passing the qualitative slope matters:
    without it the US Site score loses a feature and can drop out entirely, so the
    export's ``properties`` score would omit the Site component the app includes.
    """
    percent = soil_data.get("slopeSteepnessPercent")
    if percent is not None:
        return float(percent)
    degree = soil_data.get("slopeSteepnessDegree")
    if degree is not None:
        # percent = tan(degrees) * 100
        return round(math.tan(math.radians(degree)) * 100, 1)
    select = soil_data.get("slopeSteepnessSelect")
    if select is not None:
        return _SLOPE_SELECT_MIDPOINT_PCT.get(select)
    return None


def set_soil_id_cache_enabled(enabled):
    """Enable or disable the soil_id cache."""
    global _USE_SOIL_ID_CACHE
    with _cache_lock:
        _USE_SOIL_ID_CACHE = enabled


def cache_soil_id(site_id, soil_id_data):
    """Store soil_id data in cache for a site."""
    with _cache_lock:
        if _USE_SOIL_ID_CACHE:
            _soil_id_cache[str(site_id)] = soil_id_data


def clear_soil_id_cache():
    """Clear all cached soil_id data."""
    with _cache_lock:
        _soil_id_cache.clear()


def fetch_all_notes_for_site(site_id, request, page_size=settings.EXPORT_PAGE_SIZE):
    after = None
    notes = []
    gql = """
    query SiteNotes($id: ID!, $first: Int!, $after: String) {
      site(id: $id) {
        notes(first: $first, after: $after) {
          pageInfo { hasNextPage endCursor }
          edges {
            node {
              id
              content
              createdAt
              updatedAt
              deletedAt
              deletedByCascade
              author {
                id
                email
                firstName
                lastName
                profileImage
              }
            }
          }
        }
      }
    }
    """
    while True:
        res = schema.execute(
            gql,
            variable_values={"id": site_id, "first": page_size, "after": after},
            context_value=request,
        )
        if res.errors:
            raise RuntimeError(res.errors)
        conn = res.data["site"]["notes"]
        notes.extend(e["node"] for e in conn["edges"])
        if not conn["pageInfo"]["hasNextPage"]:
            return notes
        after = conn["pageInfo"]["endCursor"]


def fetch_site_data(site_id, request):
    # Note: The following fields are intentionally excluded from export:
    # - Depth interval enabled flags (soilStructureEnabled, phEnabled,
    #   electricalConductivityEnabled, carbonatesEnabled,
    #   soilOrganicCarbonMatterEnabled, sodiumAdsorptionRatioEnabled)
    # - Site-level fields: floodingSelect, grazingSelect, landCoverSelect,
    #   limeRequirementsSelect, waterTableDepthSelect
    # - Depth-dependent: clayPercent, conductivity, conductivityTest,
    #   conductivityUnit, structure, ph, phTestingSolution, phTestingMethod,
    #   soilOrganicCarbon, soilOrganicMatter, soilOrganicCarbonTesting,
    #   soilOrganicMatterTesting, sodiumAbsorptionRatio, carbonates
    # These fields not yet used anywhere
    gql = """
    query SiteWithNotes($id: ID!) {
        site(id: $id) {
            id
            name
            latitude
            longitude
            elevation
            privacy
            archived
            seen
            soilData {
                downSlope
                crossSlope
                bedrock
                slopeLandscapePosition
                slopeAspect
                slopeSteepnessSelect
                slopeSteepnessPercent
                slopeSteepnessDegree
                surfaceCracksSelect
                surfaceSaltSelect
                surfaceStoninessSelect
                soilDepthSelect
                depthIntervalPreset
                depthIntervals {
                    label
                    soilTextureEnabled
                    soilColorEnabled
                    depthInterval {
                        start
                        end
                    }
                }
                depthDependentData {
                    depthInterval {
                        start
                        end
                    }
                    texture
                    rockFragmentVolume
                    colorHue
                    colorValue
                    colorChroma
                    colorPhotoUsed
                    colorPhotoSoilCondition
                    colorPhotoLightingCondition
                }
            }
            soilMetadata {
               selectedSoilId
               userRatings {
                   soilMatchId
                   rating
               }
            }
            project {
                id
                name
                description
                siteInstructions
                updatedAt
                soilSettings {
                    depthIntervalPreset
                    depthIntervals {
                        label
                        depthInterval {
                            start
                            end
                        }
                    }
                }
            }
        }
    }
    """

    res = schema.execute(
        gql,
        variable_values={"id": site_id},
        context_value=request,
    )
    if res.errors:
        raise RuntimeError(res.errors)

    return res.data["site"]


def fetch_soil_id(site, request, include_explain=False):
    """Fetch soil ID data for a site using its coordinate and soil data.

    If cache is enabled and data exists for this site, returns cached data
    instead of making an external API call.

    When ``include_explain`` is set, the response also carries
    ``soilId.soilIdExplanation`` — the full scoring trace (JSON) for the ranking
    at this site — for the offline explain report.
    """
    site_id = site.get("id")

    # Check cache first (if enabled). The in-memory cache stores the non-explain
    # shape, so skip it when the trace was requested.
    if not include_explain:
        with _cache_lock:
            if _USE_SOIL_ID_CACHE and site_id and str(site_id) in _soil_id_cache:
                return _soil_id_cache[str(site_id)]

    latitude = site.get("latitude")
    longitude = site.get("longitude")

    if not latitude or not longitude:
        return {"error": "Site missing latitude or longitude"}

    # Extract soil data from the site
    soil_data = site.get("soilData", {})

    # Build the data structure for soil ID query. Pass the site's stored
    # elevation (the client-resolved value) so the ranking uses the same
    # elevation the app shows, rather than a separate server-side lookup.
    data = {
        "slope": _slope_percent(soil_data),
        "elevation": site.get("elevation"),
        "surfaceCracks": soil_data.get("surfaceCracksSelect", "NO_CRACKING"),
        "depthDependentData": [],
    }

    # Filter depth-dependent data to only include visible intervals.
    # This uses the same logic as the CSV/JSON export (process_depth_data),
    # respecting the effective preset (project overrides site).
    visible_keys = {depth_key(interval) for interval, _ in get_visible_intervals(site)}
    measurements = soil_data.get("depthDependentData", [])

    for measurement in measurements:
        if depth_key(measurement) not in visible_keys:
            continue

        di = measurement.get("depthInterval", {})
        depth_entry = {
            "depthInterval": {
                "start": di.get("start"),
                "end": di.get("end"),
            }
        }

        # Add texture if available
        if measurement.get("texture"):
            depth_entry["texture"] = measurement["texture"]

        # Add rock fragment volume if available
        if measurement.get("rockFragmentVolume"):
            depth_entry["rockFragmentVolume"] = measurement["rockFragmentVolume"]

        # Pass Munsell color straight through; the soil-ID API converts it to
        # LAB (and ignores it if out of gamut). Previously this converted to
        # colorLAB here, duplicating the API's own conversion.
        if (
            measurement.get("colorHue") is not None
            and measurement.get("colorValue") is not None
            and measurement.get("colorChroma") is not None
        ):
            depth_entry["colorMunsellNumeric"] = {
                "hue": measurement["colorHue"],
                "value": measurement["colorValue"],
                "chroma": measurement["colorChroma"],
            }

        data["depthDependentData"].append(depth_entry)

    # print("query SoilID Latitude ", latitude, "Longitude ", longitude, "Data ", data)

    # Optionally also request the full scoring trace (same lat/lon/data). Injected
    # via a placeholder so the surrounding query keeps its literal { } braces.
    explanation_field = (
        "soilIdExplanation(latitude: $latitude, longitude: $longitude, data: $data)"
        if include_explain
        else ""
    )

    # GraphQL query
    gql = """
    query SoilId($latitude: Float!, $longitude: Float!, $data: SoilIdInputData) {
        soilId {
            __EXPLANATION_FIELD__
            soilMatches(latitude: $latitude, longitude: $longitude, data: $data) {
                ... on SoilMatches {
                    dataRegion
                    matches {
                        dataSource
                        distanceToNearestMapUnitM
                        combinedMatch {
                            rank
                            score
                        }
                        dataMatch {
                            rank
                            score
                        }
                        locationMatch {
                            rank
                            score
                        }
                        soilInfo {
                            soilSeries {
                                name
                                taxonomySubgroup
                                description
                                management
                                fullDescriptionUrl
                            }
                            ecologicalSite {
                                name
                                id
                                url
                            }
                            landCapabilityClass {
                                capabilityClass
                                subClass
                            }
                            soilData {
                                slope
                                depthDependentData {
                                    depthInterval {
                                        start
                                        end
                                    }
                                    texture
                                    rockFragmentVolume
                                    munsellColorString
                                }
                            }
                        }
                    }
                }
                ... on SoilIdFailure {
                    reason
                }
            }
        }
    }
    """
    gql = gql.replace("__EXPLANATION_FIELD__", explanation_field)

    res = schema.execute(
        gql,
        variable_values={"latitude": latitude, "longitude": longitude, "data": data},
        context_value=request,
    )
    if res.errors:
        raise RuntimeError(res.errors)
    return res.data
