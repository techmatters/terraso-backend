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

from apps.graphql.schema.schema import schema


def fetch_all_notes_for_site(site_id, request, page_size=200):
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


def fetch_site_data(site_id, request, page_size=50):
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
                floodingSelect
                limeRequirementsSelect
                surfaceStoninessSelect
                waterTableDepthSelect
                soilDepthSelect
                landCoverSelect
                grazingSelect
                depthIntervalPreset
                depthIntervals {
                    label
                    soilTextureEnabled
                    soilColorEnabled
                    soilStructureEnabled
                    carbonatesEnabled
                    phEnabled
                    soilOrganicCarbonMatterEnabled
                    electricalConductivityEnabled
                    sodiumAdsorptionRatioEnabled
                    depthInterval {
                        start
                        end
                    }
                }
                depthDependentData {
                    texture
                    clayPercent
                    rockFragmentVolume
                    colorHue
                    colorValue
                    colorChroma
                    colorPhotoUsed
                    colorPhotoSoilCondition
                    colorPhotoLightingCondition
                    conductivity
                    conductivityTest
                    conductivityUnit
                    structure
                    ph
                    phTestingSolution
                    phTestingMethod
                    soilOrganicCarbon
                    soilOrganicMatter
                    soilOrganicCarbonTesting
                    soilOrganicMatterTesting
                    sodiumAbsorptionRatio
                    carbonates
                }
            }
            soilMetadata {
               selectedSoilId
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


def fetch_project_list(user_id, request, page_size=50):
    all_projects = []
    after = None
    gql = """
    query Projects($member: ID!, $first: Int!, $after: String) {
      projects(member: $member, first: $first, after: $after) {
        totalCount
        pageInfo { hasNextPage endCursor }
        edges {
          node {
            id
            name
          }
        }
      }
    }
    """
    while True:
        res = schema.execute(
            gql,
            variable_values={"member": user_id, "first": page_size, "after": after},
            context_value=request,
        )
        if res.errors:
            raise RuntimeError(res.errors)
        conn = res.data["projects"]
        batch = [e["node"] for e in conn["edges"]]
        all_projects.extend(batch)
        if not conn["pageInfo"]["hasNextPage"]:
            break
        after = conn["pageInfo"]["endCursor"]
    return all_projects


def fetch_all_sites(project_id, request, page_size=50):
    all_sites = []
    after = None
    gql = """
    query ProjectWithSites($id: ID!, $first: Int!, $after: String) {
        sites(project: $id, first: $first, after: $after) {
            pageInfo { hasNextPage endCursor }
            edges {
                cursor
                node {
                    id
                    name
                }
            }
        }
    }
    """
    while True:
        res = schema.execute(
            gql,
            variable_values={"id": project_id, "first": page_size, "after": after},
            context_value=request,
        )
        if res.errors:
            raise RuntimeError(res.errors)
        conn = res.data["sites"]
        batch = [e["node"] for e in conn["edges"]]
        all_sites.extend(batch)
        if not conn["pageInfo"]["hasNextPage"]:
            break
        after = conn["pageInfo"]["endCursor"]
    return all_sites


def fetch_soil_id(latitude, longitude, data, request):
    gql = """
    query SoilId($latitude: Float!, $longitude: Float!, $data: SoilIdInputData) {
        soilId {
            soilMatches(latitude: $latitude,longitude: $longitude, data: $data) {
                ... on SoilIdFailure {
                    reason
                }
                ... on SoilMatches {
                    dataRegion
                    
                    matches {
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
                        dataSource
                        soilInfo {
                            ecologicalSite {
                                id
                                name
                                url
                            }
                            landCapabilityClass {
                                capabilityClass
                                subClass
                            }
                            soilData {
                                depthDependentData {
                                    depthInterval {
                                        start
                                        end
                                    }
                                    munsellColorString
                                    rockFragmentVolume
                                    texture
                                }
                                slope
                            }
                            soilSeries {
                                name
                                taxonomySubgroup
                                description
                                fullDescriptionUrl
                            }
                        }
                    }
                }
            }
        }
    }
    """
    gql = """
    query SoilId($latitude: Float!, $longitude: Float!) {
        soilId {
            soilMatches(latitude: $latitude, longitude: $longitude, data: {slope:15, surfaceCracks:NO_CRACKING, depthDependentData: []}) {
                ... on SoilMatches {
                    dataRegion
                    matches {
                        dataSource
                        distanceToNearestMapUnitM
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
        variable_values={"latitude": latitude, "longitude": longitude},
        context_value=request,
    )
    if res.errors:
        raise RuntimeError(res.errors)
    return res.data; 
