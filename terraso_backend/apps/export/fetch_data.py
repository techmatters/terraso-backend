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

from django.conf import settings

from apps.graphql.schema.schema import schema


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
            updatedAt
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
    # Fetch soil ID data for a site using its coordinate and soil data.
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

    # Process depth intervals and depth-dependent data
    depth_intervals = soil_data.get("depthIntervals", [])
    depth_dependent_data = soil_data.get("depthDependentData", [])

    for interval, depth_data in zip(depth_intervals, depth_dependent_data):
        depth_entry = {
            "depthInterval": {
                "start": interval.get("depthInterval", {}).get("start"),
                "end": interval.get("depthInterval", {}).get("end"),
            }
        }

        # Add texture if available
        if depth_data.get("texture"):
            depth_entry["texture"] = depth_data["texture"]

        # Add rock fragment volume if available
        if depth_data.get("rockFragmentVolume"):
            depth_entry["rockFragmentVolume"] = depth_data["rockFragmentVolume"]

        # Convert Munsell color to LAB color if available
        if (
            depth_data.get("colorHue") is not None
            and depth_data.get("colorValue") is not None
            and depth_data.get("colorChroma") is not None
        ):
            # For now, we'll use placeholder LAB values
            # In a real implementation, you'd convert Munsell to LAB
            depth_entry["colorLAB"] = {
                "L": depth_data.get("colorValue", 0) * 10,  # Rough conversion
                "A": 0.0,  # Placeholder
                "B": depth_data.get("colorChroma", 0) * 2,  # Rough conversion
            }

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
