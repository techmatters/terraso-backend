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
Round-trip tests for export transformation pipeline.

These tests:
1. Load raw JSON fixtures into the database
2. Run the export (which fetches data via GraphQL and transforms it)
3. Compare the output against expected results

This ensures the transformation pipeline produces consistent, expected output
from known input data.
"""

import json

import pytest

from apps.export.models import ExportToken
from apps.export.transformers import (
    apply_object_transformations,
    flatten_site,
    process_depth_data,
)

from .fixture_loader import create_user_for_fixtures, load_site_from_raw_json

pytestmark = pytest.mark.django_db


# Minimal inline fixture for transformation tests (no external file dependency)
MINIMAL_SITE_DATA = {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "name": "Test Site Alpha",
    "latitude": 40.5,
    "longitude": -105.2,
    "elevation": 1650.0,
    "updatedAt": "2024-01-15T10:30:00Z",
    "privacy": "PRIVATE",
    "archived": False,
    "soilData": {
        "downSlope": "CONCAVE",
        "crossSlope": "CONVEX",
        "slopeAspect": 180,
        "slopeSteepnessSelect": "FLAT",
        "slopeSteepnessPercent": 1.5,
        "slopeSteepnessDegree": 0.86,
        "surfaceCracksSelect": "NO_CRACKING",
        "depthIntervalPreset": "NRCS",
        "depthIntervals": [
            {
                "label": "0-5 cm",
                "soilTextureEnabled": True,
                "soilColorEnabled": True,
                "depthInterval": {"start": 0, "end": 5},
            },
            {
                "label": "5-15 cm",
                "soilTextureEnabled": True,
                "soilColorEnabled": True,
                "depthInterval": {"start": 5, "end": 15},
            },
        ],
        "depthDependentData": [
            {
                "depthInterval": {"start": 0, "end": 5},
                "texture": "SILTY_CLAY",
                "rockFragmentVolume": "VOLUME_0_1",
                "colorHue": 25.0,
                "colorValue": 4.0,
                "colorChroma": 3.0,
                "colorPhotoUsed": True,
                "colorPhotoSoilCondition": "MOIST",
                "colorPhotoLightingCondition": "EVEN",
            },
            {
                "depthInterval": {"start": 5, "end": 15},
                "texture": "CLAY_LOAM",
                "rockFragmentVolume": "VOLUME_1_15",
                "colorHue": 25.0,
                "colorValue": 5.0,
                "colorChroma": 4.0,
                "colorPhotoUsed": False,
            },
        ],
    },
    "soilMetadata": {"selectedSoilId": "Test Soil Series"},
    "project": {
        "id": "11111111-2222-3333-4444-555566667777",
        "name": "Test Project",
        "description": "A test project for export testing",
    },
    "notes": [
        {
            "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "content": "First observation note",
            "createdAt": "2024-01-10T08:00:00Z",
            "author": {
                "email": "test@example.com",
                "firstName": "Test",
                "lastName": "User",
            },
        }
    ],
}


def create_test_site(owner):
    """Create a test site from inline fixture data."""
    return load_site_from_raw_json(MINIMAL_SITE_DATA.copy(), owner)


class TestTransformationPipeline:
    """Tests for the data transformation functions."""

    def test_export_enum_code_to_label_transformation(self):
        """Test that enum codes are converted to human-readable labels."""
        data = {
            "texture": "SILTY_CLAY",
            "rockFragmentVolume": "VOLUME_0_1",
            "surfaceCracksSelect": "NO_CRACKING",
        }

        apply_object_transformations(data)

        assert data["texture"] == "Silty Clay"
        assert data["rockFragmentVolume"] == "0-1%"
        # Label uses sentence case per Django TextChoices definition
        assert data["surfaceCracksSelect"] == "No cracking"

    def test_export_munsell_color_generation(self):
        """Test that Munsell color string is generated from color components."""
        # Use hue=7.5 which maps to 7.5R (hue_index=0, substep=3 -> 7.5)
        data = {
            "colorHue": 7.5,
            "colorValue": 4.0,
            "colorChroma": 3.0,
        }

        apply_object_transformations(data)

        assert "_colorMunsell" in data
        # 7.5 hue -> 7.5R
        assert "R" in data["_colorMunsell"]
        assert "4/3" in data["_colorMunsell"]

    def test_export_depth_intervals_with_measurements(self):
        """Test that export includes visible intervals with _depthSource and merged measurements."""
        site = {
            "project": None,
            "soilData": {
                "depthIntervalPreset": "CUSTOM",
                "depthIntervals": [
                    {"label": "0-5 cm", "depthInterval": {"start": 0, "end": 5}},
                    {"label": "5-15 cm", "depthInterval": {"start": 5, "end": 15}},
                ],
                "depthDependentData": [
                    {"depthInterval": {"start": 0, "end": 5}, "texture": "CLAY"},
                    {"depthInterval": {"start": 5, "end": 15}, "texture": "LOAM"},
                ],
            },
        }

        process_depth_data(site)

        soil_data = site["soilData"]

        # depthIntervals should be removed
        assert "depthIntervals" not in soil_data

        # depthDependentData should have flattened data with _depthSource
        assert len(soil_data["depthDependentData"]) == 2
        assert soil_data["depthDependentData"][0]["label"] == "0-5 cm"
        assert soil_data["depthDependentData"][0]["depthIntervalStart"] == 0
        assert soil_data["depthDependentData"][0]["depthIntervalEnd"] == 5
        assert soil_data["depthDependentData"][0]["texture"] == "CLAY"
        assert soil_data["depthDependentData"][0]["_depthSource"] == "CUSTOM"

    def test_export_depth_intervals_includes_empty(self):
        """Test that export includes all visible intervals, even ones without measurements."""
        site = {
            "project": None,
            "soilData": {
                "depthIntervalPreset": "CUSTOM",
                "depthIntervals": [
                    {"label": "0-5 cm", "depthInterval": {"start": 0, "end": 5}},
                    {"label": "5-15 cm", "depthInterval": {"start": 5, "end": 15}},
                    {"label": "15-30 cm", "depthInterval": {"start": 15, "end": 30}},
                ],
                "depthDependentData": [
                    # Only first interval has data
                    {"depthInterval": {"start": 0, "end": 5}, "texture": "CLAY"},
                ],
            },
        }

        process_depth_data(site)

        soil_data = site["soilData"]

        # Output should have all 3 intervals, even empty ones
        assert len(soil_data["depthDependentData"]) == 3

        # First interval has data
        assert soil_data["depthDependentData"][0]["depthIntervalStart"] == 0
        assert soil_data["depthDependentData"][0]["texture"] == "CLAY"

        # Second interval is empty (no measurement)
        assert soil_data["depthDependentData"][1]["depthIntervalStart"] == 5
        assert soil_data["depthDependentData"][1].get("texture") is None

        # Third interval is empty
        assert soil_data["depthDependentData"][2]["depthIntervalStart"] == 15

    def test_export_orphaned_measurements_dropped(self):
        """Test that measurements without matching intervals are dropped."""
        site = {
            "project": None,
            "soilData": {
                "depthIntervalPreset": "CUSTOM",
                "depthIntervals": [
                    {"label": "0-5 cm", "depthInterval": {"start": 0, "end": 5}},
                ],
                "depthDependentData": [
                    # This matches the interval
                    {"depthInterval": {"start": 0, "end": 5}, "texture": "CLAY"},
                    # This is orphaned - no matching interval
                    {"depthInterval": {"start": 50, "end": 100}, "texture": "SAND"},
                ],
            },
        }

        process_depth_data(site)

        soil_data = site["soilData"]

        # Only the one defined interval should be in output
        assert len(soil_data["depthDependentData"]) == 1
        assert soil_data["depthDependentData"][0]["depthIntervalStart"] == 0
        assert soil_data["depthDependentData"][0]["texture"] == "CLAY"

    def test_export_empty_interval_included(self):
        """Test that intervals without measurements are still included."""
        site = {
            "project": None,
            "soilData": {
                "depthIntervalPreset": "CUSTOM",
                "depthIntervals": [
                    {"label": "0-5 cm", "depthInterval": {"start": 0, "end": 5}},
                    {"label": "5-15 cm", "depthInterval": {"start": 5, "end": 15}},
                ],
                "depthDependentData": [
                    # Only first interval has measurement
                    {"depthInterval": {"start": 0, "end": 5}, "texture": "CLAY"},
                ],
            },
        }

        process_depth_data(site)

        soil_data = site["soilData"]

        # Both intervals should be in output
        assert len(soil_data["depthDependentData"]) == 2

        # First has measurement
        assert soil_data["depthDependentData"][0]["depthIntervalStart"] == 0
        assert soil_data["depthDependentData"][0]["texture"] == "CLAY"

        # Second is empty but still included
        assert soil_data["depthDependentData"][1]["depthIntervalStart"] == 5
        assert soil_data["depthDependentData"][1].get("texture") is None

    def test_export_rock_fragment_volume_formatting(self):
        """Test that rock fragment volume uses simple dash format."""
        data = {"rockFragmentVolume": "VOLUME_0_1"}

        apply_object_transformations(data)

        # Should be "0-1%" not "0 — 1%"
        assert data["rockFragmentVolume"] == "0-1%"
        assert "—" not in data["rockFragmentVolume"]
        assert " " not in data["rockFragmentVolume"]

    def test_export_slope_steepness_formatting(self):
        """Test that slope steepness uses dash without spaces."""
        data = {"slopeSteepnessSelect": "FLAT"}

        apply_object_transformations(data)

        # Should be "0-2% (flat)" not "0 - 2% (flat)"
        value = data["slopeSteepnessSelect"]
        assert "0-2%" in value
        assert " - " not in value


class TestFixtureRoundTrip:
    """Round-trip tests using inline fixture data."""

    @pytest.fixture
    def test_site_export(self):
        """Create a test site with export token and return (site, url_base)."""
        owner = create_user_for_fixtures()
        site = create_test_site(owner)
        token = ExportToken.create_token("SITE", str(site.id), str(owner.id))
        url_base = f"/export/token/site/{token.token}/test"
        return site, url_base

    def test_export_load_fixture_and_export(self, client, test_site_export):
        """Test loading fixture data and running export."""
        site, url_base = test_site_export
        response = client.get(f"{url_base}.json")

        assert response.status_code == 200

        data = json.loads(response.content)
        assert "sites" in data
        assert len(data["sites"]) == 1

        exported_site = data["sites"][0]
        assert exported_site["id"] == str(site.id)
        assert exported_site["name"] == "Test Site Alpha"

    def test_export_transformation_output_structure(self, client, test_site_export):
        """Test that transformed output has expected structure."""
        _, url_base = test_site_export
        response = client.get(f"{url_base}.json")

        data = json.loads(response.content)
        exported = data["sites"][0]

        # Check top-level fields exist
        assert "id" in exported
        assert "name" in exported
        assert "latitude" in exported
        assert "longitude" in exported

        # Check soil data structure
        assert "soilData" in exported
        soil_data = exported["soilData"]

        # depthIntervals should be merged into depthDependentData
        assert "depthDependentData" in soil_data

        # Check depth dependent data has merged structure
        if soil_data["depthDependentData"]:
            dd = soil_data["depthDependentData"][0]
            # Should have interval metadata
            assert "label" in dd
            assert "depthIntervalStart" in dd
            assert "depthIntervalEnd" in dd

    def test_export_enum_labels_in_export(self, client, test_site_export):
        """Test that exported data has human-readable labels, not codes."""
        _, url_base = test_site_export
        response = client.get(f"{url_base}.json")

        data = json.loads(response.content)
        exported = data["sites"][0]
        soil_data = exported["soilData"]

        # Check enum fields are transformed to labels
        assert soil_data.get("downSlope") == "Concave"
        assert soil_data.get("crossSlope") == "Convex"
        # Label uses sentence case per Django TextChoices definition
        assert soil_data.get("surfaceCracksSelect") == "No cracking"

        # Check depth dependent data
        if soil_data["depthDependentData"]:
            dd = soil_data["depthDependentData"][0]
            assert dd.get("texture") == "Silty Clay"
            assert dd.get("rockFragmentVolume") == "0-1%"

    def test_export_notes_included_in_export(self, client, test_site_export):
        """Test that notes are included in the export."""
        _, url_base = test_site_export
        response = client.get(f"{url_base}.json")

        data = json.loads(response.content)
        exported = data["sites"][0]

        assert "notes" in exported
        assert len(exported["notes"]) >= 1
        note = exported["notes"][0]
        assert "content" in note
        assert "author" in note

    def test_export_csv_has_expected_columns(self, client, test_site_export):
        """Test that CSV export has expected column headers."""
        _, url_base = test_site_export
        response = client.get(f"{url_base}.csv")

        assert response.status_code == 200
        content = response.content.decode("utf-8")

        # Check for expected CSV headers
        expected_headers = [
            "Site ID",
            "Site name",
            "Latitude",
            "Longitude",
            "Depth label",
            "Depth texture class",
            "Depth soil color",
        ]
        for header in expected_headers:
            assert header in content, f"Missing header: {header}"


class TestFlattenSite:
    """Tests for the flatten_site function used in CSV generation."""

    def test_export_flatten_produces_rows_per_depth_interval(self):
        """Test that flatten_site produces one row per depth interval."""
        site = {
            "id": "test-id",
            "name": "Test Site",
            "latitude": 40.0,
            "longitude": -105.0,
            "elevation": 1600,
            "updatedAt": "2024-01-01T00:00:00Z",
            "privacy": "PRIVATE",
            "project": None,
            "soilData": {
                "depthIntervalPreset": "NRCS",
                "depthDependentData": [
                    {"label": "0-5 cm", "depthIntervalStart": 0, "depthIntervalEnd": 5},
                    {"label": "5-15 cm", "depthIntervalStart": 5, "depthIntervalEnd": 15},
                ],
            },
            "soilMetadata": {},
            "notes": [],
            "soil_id": {},
        }

        rows = flatten_site(site)

        assert len(rows) == 2
        assert rows[0]["Depth label"] == "0-5 cm"
        assert rows[1]["Depth label"] == "5-15 cm"

    def test_export_flatten_handles_empty_depth_data(self):
        """Test that flatten produces at least one row even with no depth data."""
        site = {
            "id": "test-id",
            "name": "Test Site",
            "latitude": 40.0,
            "longitude": -105.0,
            "elevation": 1600,
            "updatedAt": "2024-01-01T00:00:00Z",
            "privacy": "PRIVATE",
            "project": None,
            "soilData": {
                "depthDependentData": [],
            },
            "soilMetadata": {},
            "notes": [],
            "soil_id": {},
        }

        rows = flatten_site(site)

        assert len(rows) == 1
        assert rows[0]["Site ID"] == "test-id"
