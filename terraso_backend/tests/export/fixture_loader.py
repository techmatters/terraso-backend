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

"""
Fixture loader for export tests.

Loads raw JSON fixture data (from ?format=raw export) into the database
for round-trip testing of the export transformation pipeline.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

from apps.core.models import User
from apps.export.fetch_data import cache_soil_id
from apps.project_management.models import Project, Site, SiteNote
from apps.soil_id.models import (
    DepthDependentSoilData,
    ProjectDepthInterval,
    ProjectSoilSettings,
    SoilData,
    SoilDataDepthInterval,
    SoilMetadata,
)


def parse_datetime(dt_str):
    """Parse ISO datetime string to timezone-aware datetime."""
    if not dt_str:
        return None
    # Handle both Z suffix and +00:00 format
    if dt_str.endswith("Z"):
        dt_str = dt_str[:-1] + "+00:00"
    return datetime.fromisoformat(dt_str)


def load_fixture_file(fixture_name, fixtures_dir=None):
    """Load a fixture JSON file from the fixtures directory."""
    if fixtures_dir is None:
        fixtures_dir = Path(__file__).parent / "fixtures"
    fixture_path = fixtures_dir / fixture_name
    with open(fixture_path) as f:
        return json.load(f)


def create_user_for_fixtures(email="fixture-user@test.com"):
    """Create or get a user for fixture data."""
    user, _ = User.objects.get_or_create(
        email=email,
        defaults={
            "first_name": "Fixture",
            "last_name": "User",
        },
    )
    return user


def create_project_soil_settings(project, soil_settings_data):
    """
    Create ProjectSoilSettings and ProjectDepthInterval records for a project.

    Args:
        project: Project instance
        soil_settings_data: Dict with depthIntervalPreset and optional depthIntervals
    """
    if not soil_settings_data:
        return None

    preset = soil_settings_data.get("depthIntervalPreset")
    if not preset:
        return None

    soil_settings, _ = ProjectSoilSettings.objects.get_or_create(
        project=project,
        defaults={"depth_interval_preset": preset},
    )

    # Update preset if it already existed
    if soil_settings.depth_interval_preset != preset:
        soil_settings.depth_interval_preset = preset
        soil_settings.save()

    # Create custom depth intervals if present
    depth_intervals = soil_settings_data.get("depthIntervals", [])
    for interval_data in depth_intervals:
        interval_obj = interval_data.get("depthInterval", {})
        ProjectDepthInterval.objects.get_or_create(
            project=soil_settings,
            depth_interval_start=interval_obj.get("start"),
            depth_interval_end=interval_obj.get("end"),
            defaults={"label": interval_data.get("label", "")},
        )

    return soil_settings


def load_site_from_raw_json(site_data, owner, synthetic_project=None):
    """
    Load a single site from raw JSON format into the database.

    Args:
        site_data: Dict from raw JSON export (format=raw)
        owner: User who will own the site
        synthetic_project: Project to assign to this site (overrides any project in data)
                          Used for multi-site fixtures where all sites must be in same project

    Returns:
        The created Site instance
    """
    # Use synthetic project if provided (for multi-site fixtures)
    # Otherwise create/use the project from the data
    project = None
    if synthetic_project:
        project = synthetic_project
    else:
        project_data = site_data.get("project")
        if project_data:
            project_id = project_data.get("id")
            if project_id:
                project, created = Project.objects.get_or_create(
                    id=project_id,
                    defaults={
                        "name": project_data.get("name", ""),
                        "description": project_data.get("description", ""),
                        "site_instructions": project_data.get("siteInstructions"),
                    },
                )
                # Update site_instructions if project already existed
                if not created and project_data.get("siteInstructions"):
                    project.site_instructions = project_data["siteInstructions"]
                    project.save()
                # Update project timestamps if provided
                if project_data.get("updatedAt"):
                    Project.objects.filter(id=project.id).update(
                        updated_at=parse_datetime(project_data["updatedAt"])
                    )
                # Ensure owner is a manager
                if not project.is_manager(owner):
                    project.add_manager(owner)
                # Create project soil settings if present
                soil_settings_data = project_data.get("soilSettings")
                if soil_settings_data:
                    create_project_soil_settings(project, soil_settings_data)

    # Create site with specified ID
    site_id = site_data.get("id")
    site = Site.objects.create(
        id=site_id if site_id else uuid.uuid4(),
        name=site_data.get("name", ""),
        latitude=site_data.get("latitude"),
        longitude=site_data.get("longitude"),
        elevation=site_data.get("elevation"),
        privacy=site_data.get("privacy", "PRIVATE"),
        archived=site_data.get("archived", False),
        owner=owner if not project else None,
        project=project,
    )

    # Update timestamps if provided
    if site_data.get("updatedAt"):
        Site.objects.filter(id=site.id).update(updated_at=parse_datetime(site_data["updatedAt"]))

    # Create SoilData
    soil_data_json = site_data.get("soilData", {})
    if soil_data_json:
        soil_data = SoilData.objects.create(
            site=site,
            down_slope=soil_data_json.get("downSlope"),
            cross_slope=soil_data_json.get("crossSlope"),
            bedrock=soil_data_json.get("bedrock"),
            slope_landscape_position=soil_data_json.get("slopeLandscapePosition"),
            slope_aspect=soil_data_json.get("slopeAspect"),
            slope_steepness_select=soil_data_json.get("slopeSteepnessSelect"),
            slope_steepness_percent=soil_data_json.get("slopeSteepnessPercent"),
            slope_steepness_degree=soil_data_json.get("slopeSteepnessDegree"),
            surface_cracks_select=soil_data_json.get("surfaceCracksSelect"),
            surface_salt_select=soil_data_json.get("surfaceSaltSelect"),
            surface_stoniness_select=soil_data_json.get("surfaceStoninessSelect"),
            soil_depth_select=soil_data_json.get("soilDepthSelect"),
            depth_interval_preset=soil_data_json.get("depthIntervalPreset"),
        )

        # Create SoilDataDepthInterval records (custom interval metadata)
        # These store label, enabled flags, and interval bounds for CUSTOM presets
        depth_intervals = soil_data_json.get("depthIntervals", [])
        for interval_data in depth_intervals:
            interval_obj = interval_data.get("depthInterval", {})
            SoilDataDepthInterval.objects.create(
                soil_data=soil_data,
                label=interval_data.get("label", ""),
                depth_interval_start=interval_obj.get("start"),
                depth_interval_end=interval_obj.get("end"),
                soil_texture_enabled=interval_data.get("soilTextureEnabled"),
                soil_color_enabled=interval_data.get("soilColorEnabled"),
                soil_structure_enabled=interval_data.get("soilStructureEnabled"),
                carbonates_enabled=interval_data.get("carbonatesEnabled"),
                ph_enabled=interval_data.get("phEnabled"),
                soil_organic_carbon_matter_enabled=interval_data.get(
                    "soilOrganicCarbonMatterEnabled"
                ),
                electrical_conductivity_enabled=interval_data.get("electricalConductivityEnabled"),
                sodium_adsorption_ratio_enabled=interval_data.get("sodiumAdsorptionRatioEnabled"),
            )

        # Create DepthDependentSoilData (actual measurement data)
        depth_dependent = soil_data_json.get("depthDependentData", [])

        for dd_data in depth_dependent:
            # Get interval bounds from depthInterval object (raw GraphQL format)
            interval = dd_data.get("depthInterval", {})
            interval_start = interval.get("start")
            interval_end = interval.get("end")

            DepthDependentSoilData.objects.create(
                soil_data=soil_data,
                depth_interval_start=interval_start,
                depth_interval_end=interval_end,
                texture=dd_data.get("texture"),
                rock_fragment_volume=dd_data.get("rockFragmentVolume"),
                color_hue=dd_data.get("colorHue"),
                color_value=dd_data.get("colorValue"),
                color_chroma=dd_data.get("colorChroma"),
                color_photo_used=dd_data.get("colorPhotoUsed"),
                color_photo_soil_condition=dd_data.get("colorPhotoSoilCondition"),
                color_photo_lighting_condition=dd_data.get("colorPhotoLightingCondition"),
            )

    # Create SoilMetadata
    soil_metadata_json = site_data.get("soilMetadata", {})
    if soil_metadata_json:
        # Read userRatings array from raw export and convert to dict format
        # Raw format: [{"soilMatchId": "name", "rating": "SELECTED"}, ...]
        # Model format: {"name": "SELECTED", ...}
        user_ratings_list = soil_metadata_json.get("userRatings", [])
        user_ratings = {
            entry["soilMatchId"]: entry["rating"]
            for entry in user_ratings_list
            if "soilMatchId" in entry and "rating" in entry
        }
        if user_ratings:
            SoilMetadata.objects.create(
                site=site,
                user_ratings=user_ratings,
            )

    # Create notes
    notes_json = site_data.get("notes", [])
    for note_data in notes_json:
        # Get or create author
        author_data = note_data.get("author", {})
        author_email = author_data.get("email", owner.email)
        author, _ = User.objects.get_or_create(
            email=author_email,
            defaults={
                "first_name": author_data.get("firstName", ""),
                "last_name": author_data.get("lastName", ""),
            },
        )

        note = SiteNote.objects.create(
            site=site,
            content=note_data.get("content", ""),
            author=author,
        )
        # Update timestamps
        if note_data.get("createdAt"):
            SiteNote.objects.filter(id=note.id).update(
                created_at=parse_datetime(note_data["createdAt"])
            )

    # Cache soil_id data if present in the raw fixture
    # This allows tests to skip external API calls during export
    if "soil_id" in site_data:
        cache_soil_id(site.id, site_data["soil_id"])

    return site


def load_sites_from_fixture(fixture_name, owner=None, fixtures_dir=None):
    """
    Load all sites from a fixture file.

    For multi-site fixtures, creates a synthetic project to contain ALL sites,
    enabling project-based export in tests. This is necessary because the test
    framework exports via project token, so all sites must be in the same project.

    Args:
        fixture_name: Name of fixture file in fixtures directory
        owner: Optional user to own the sites (creates default if None)
        fixtures_dir: Optional custom fixtures directory path

    Returns:
        List of Site instances (all in a synthetic project if multi-site)
    """
    if owner is None:
        owner = create_user_for_fixtures()

    data = load_fixture_file(fixture_name, fixtures_dir)
    sites_data = data.get("sites", [])
    sites = []

    # For multi-site fixtures, create a synthetic project for ALL sites
    # This ensures they can all be exported together via a project token
    synthetic_project = None
    if len(sites_data) > 1:
        # Get siteInstructions and soilSettings from first site's project if available
        first_project = sites_data[0].get("project", {})
        synthetic_project = Project.objects.create(
            name=f"Test Project for {fixture_name}",
            description="Synthetic project created for fixture testing",
            site_instructions=first_project.get("siteInstructions"),
        )
        synthetic_project.add_manager(owner)
        # Update timestamps if provided
        if first_project.get("updatedAt"):
            Project.objects.filter(id=synthetic_project.id).update(
                updated_at=parse_datetime(first_project["updatedAt"])
            )
        # Create project soil settings if present
        soil_settings_data = first_project.get("soilSettings")
        if soil_settings_data:
            create_project_soil_settings(synthetic_project, soil_settings_data)

    for site_data in sites_data:
        site = load_site_from_raw_json(site_data, owner, synthetic_project=synthetic_project)
        sites.append(site)

    return sites
