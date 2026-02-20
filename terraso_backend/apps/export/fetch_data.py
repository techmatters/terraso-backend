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

import csv
import os

import structlog
from django.conf import settings

from apps.graphql.schema.schema import schema

from .depth_helpers import depth_key, get_visible_intervals

logger = structlog.get_logger(__name__)

# In-memory cache for soil_id data, used to avoid external API calls during tests.
# Keyed by site ID (string UUID).
_soil_id_cache = {}

# Set to False to disable cache (for development/testing without cache)
_USE_SOIL_ID_CACHE = True

# Munsell-to-CIELAB lookup table, loaded lazily from the soil-id data files.
# Keyed by (hue_string, value_int, chroma_int) -> (L, A, B)
_munsell_lab_table = None

# Hue letter names in order, matching the app's colorHue (0-100) encoding
_HUE_NAMES = ["R", "YR", "Y", "GY", "G", "BG", "B", "PB", "P", "RP"]


def _load_munsell_lab_table():
    """Load the Munsell-to-CIELAB lookup table from the soil-id data files."""
    global _munsell_lab_table
    if _munsell_lab_table is not None:
        return _munsell_lab_table

    try:
        from soil_id.config import MUNSELL_RGB_LAB_PATH

        path = MUNSELL_RGB_LAB_PATH
    except ImportError:
        path = os.path.join(os.environ.get("DATA_PATH", "Data"), "LandPKS_munsell_rgb_lab.csv")

    table = {}
    try:
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                hue = row["hue"]
                value = int(row["value"])
                chroma = int(row["chroma"])
                table[(hue, value, chroma)] = (
                    float(row["cielab_l"]),
                    float(row["cielab_a"]),
                    float(row["cielab_b"]),
                )
    except FileNotFoundError:
        logger.warning("Munsell-to-LAB lookup table not found", path=path)
        table = {}

    _munsell_lab_table = table
    return _munsell_lab_table


def munsell_to_lab(color_hue, color_value, color_chroma):
    """Convert app colorHue/colorValue/colorChroma to CIELAB using the lookup table.

    Returns (L, A, B) tuple, or None if the color can't be looked up.
    """
    table = _load_munsell_lab_table()
    if not table:
        return None

    chroma = round(color_chroma)
    value = round(color_value)

    # Neutral color (chroma == 0)
    if chroma == 0:
        result = table.get(("N", value, 0))
        return result

    # Decode colorHue (0-100 continuous) to Munsell hue string
    hue = color_hue
    if hue == 100:
        hue = 0

    hue_index = int(hue // 10)
    substep = round((hue % 10) / 2.5)

    if substep == 0:
        hue_index = (hue_index + 9) % 10
        substep = 4

    substep = (substep * 5) / 2
    hue_str = f"{substep:g}{_HUE_NAMES[hue_index]}"

    return table.get((hue_str, value, chroma))


def set_soil_id_cache_enabled(enabled):
    """Enable or disable the soil_id cache."""
    global _USE_SOIL_ID_CACHE
    _USE_SOIL_ID_CACHE = enabled


def cache_soil_id(site_id, soil_id_data):
    """Store soil_id data in cache for a site."""
    if _USE_SOIL_ID_CACHE:
        _soil_id_cache[str(site_id)] = soil_id_data


def clear_soil_id_cache():
    """Clear all cached soil_id data."""
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


def fetch_soil_id(site, request):
    """Fetch soil ID data for a site using its coordinate and soil data.

    If cache is enabled and data exists for this site, returns cached data
    instead of making an external API call.
    """
    site_id = site.get("id")

    # Check cache first (if enabled)
    if _USE_SOIL_ID_CACHE and site_id and str(site_id) in _soil_id_cache:
        return _soil_id_cache[str(site_id)]

    latitude = site.get("latitude")
    longitude = site.get("longitude")

    if not latitude or not longitude:
        return {"error": "Site missing latitude or longitude"}

    # Extract soil data from the site
    soil_data = site.get("soilData", {})

    # Build the data structure for soil ID query
    data = {
        "slope": soil_data.get("slopeSteepnessDegree"),
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

        # Convert Munsell color to LAB color if available
        if (
            measurement.get("colorHue") is not None
            and measurement.get("colorValue") is not None
            and measurement.get("colorChroma") is not None
        ):
            lab = munsell_to_lab(
                measurement["colorHue"],
                measurement["colorValue"],
                measurement["colorChroma"],
            )
            if lab:
                depth_entry["colorLAB"] = {"L": lab[0], "A": lab[1], "B": lab[2]}

        data["depthDependentData"].append(depth_entry)

    # print("query SoilID Latitude ", latitude, "Longitude ", longitude, "Data ", data)

    # GraphQL query
    gql = """
    query SoilId($latitude: Float!, $longitude: Float!, $data: SoilIdInputData) {
        soilId {
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

    res = schema.execute(
        gql,
        variable_values={"latitude": latitude, "longitude": longitude, "data": data},
        context_value=request,
    )
    if res.errors:
        raise RuntimeError(res.errors)
    return res.data
