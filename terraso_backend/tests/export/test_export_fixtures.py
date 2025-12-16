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
Fixture-based export tests.

These tests automatically discover fixture files in the fixtures directory
and run export comparisons against expected output.

Fixture naming convention:
    <name>.raw.json  - Raw GraphQL input data (from ?format=raw export)
    <name>.json      - Expected JSON export output
    <name>.csv       - Expected CSV export output

To add a new test case, simply add files following this naming convention.
The test will automatically pick them up.

Generating fixtures from a real database:
    # Get raw input data
    curl "https://api.example.com/export/token/site/{token}/name.json?format=raw" > name.raw.json

    # Get expected outputs
    curl "https://api.example.com/export/token/site/{token}/name.json" > name.json
    curl "https://api.example.com/export/token/site/{token}/name.csv" > name.csv

Environment variables:
    SAVE_FAILING_OUTPUT=1  - Save actual output to <name>.actual.json/.csv for manual diff
"""

import csv
import io
import json
import os
from pathlib import Path

import pytest
from deepdiff import DeepDiff

from apps.export.models import ExportToken

from .fixture_loader import create_user_for_fixtures, load_sites_from_fixture

# Fields to ignore in JSON comparisons (may differ between test runs)
IGNORE_JSON_FIELDS = {
    "updatedAt",
    "createdAt",
    "deletedAt",
    "seen",
    "profileImage",
    "project",
    "soilMetadata",
    "userRating",
    "_selectedSoilName",
}

# Columns to ignore in CSV comparisons
IGNORE_CSV_COLUMNS = {
    "Last updated (UTC)",
    "Project name",
    "Project ID",
    "Project description",
    "Top match user rating",
}

# Additional soil-related columns to ignore when not comparing soil data
SOIL_CSV_COLUMNS = {
    "Soil map",
    "Top soil series match",
    "Top soil match taxonomy subgroup",
    "Top soil match description",
    "Ecological site name",
    "Ecological site ID",
    "Land capability classification",
    "Selected soil type taxonomy subgroup",
    "Selected soil description",
}

pytestmark = pytest.mark.django_db

FIXTURES_DIR = Path(__file__).parent / "fixtures"
WITH_SOIL_DIR = FIXTURES_DIR / "with_soil"
WITHOUT_SOIL_DIR = FIXTURES_DIR / "without_soil"


def should_save_failing_output():
    """Check if failing output should be saved (checked at runtime for Docker compatibility)."""
    return os.environ.get("SAVE_FAILING_OUTPUT", "").lower() in ("1", "true", "yes")


def format_deepdiff_path(path):
    """Convert DeepDiff path like root['sites'][0]['name'] to sites[0].name."""
    return path.replace("root", "").replace("['", ".").replace("']", "").replace("[", "[").lstrip(".")


def diff_contains_soil_id(diff):
    """Check if any diff paths contain 'soil_id'."""
    diff_str = str(diff)
    return "soil_id" in diff_str


DIFF_MESSAGES = {
    "dictionary_item_added": "unexpected key in actual",
    "dictionary_item_removed": "missing key in actual",
    "iterable_item_added": "item added in actual",
    "iterable_item_removed": "item missing in actual",
}


def format_diff_items(diff, max_items=20):
    """Format DeepDiff results into readable lines."""
    lines = []

    for change_type, changes in diff.items():
        if len(lines) >= max_items:
            break

        if change_type == "values_changed":
            for path, change in changes.items():
                if len(lines) >= max_items:
                    break
                clean_path = format_deepdiff_path(path)
                old = str(change["old_value"])[:50]
                new = str(change["new_value"])[:50]
                lines.append(f"{clean_path}: {old!r} != {new!r}")

        elif change_type == "type_changes":
            for path, change in changes.items():
                if len(lines) >= max_items:
                    break
                clean_path = format_deepdiff_path(path)
                old_type = type(change["old_value"]).__name__
                new_type = type(change["new_value"]).__name__
                lines.append(f"{clean_path}: type changed from {old_type} to {new_type}")

        elif change_type in DIFF_MESSAGES:
            for path in changes:
                if len(lines) >= max_items:
                    break
                lines.append(f"{format_deepdiff_path(path)}: {DIFF_MESSAGES[change_type]}")

    return lines


def format_json_failure_message(fixture_name, expected, actual, fixture_dir, format_type="json"):
    """Format a helpful failure message for JSON comparison failures."""
    lines = [f"JSON export mismatch for {fixture_name}"]

    diff = DeepDiff(expected, actual, ignore_order=False)
    soil_id_differs = diff_contains_soil_id(diff)

    # Count total differences
    total_diffs = sum(len(v) if isinstance(v, dict) else 1 for v in diff.values())
    lines.append(f"Total differences: {total_diffs}")

    if soil_id_differs:
        lines.append("NOTE: soil_id data differs (external API response may have changed)")

    # Format diff items
    diff_lines = format_diff_items(diff)
    for line in diff_lines:
        lines.append(f"  - {line}")

    if total_diffs > 20:
        lines.append(f"  ... and {total_diffs - 20} more")

    # Save actual output if enabled
    if should_save_failing_output():
        actual_file = fixture_dir / f"{fixture_name}.actual.{format_type}"
        with open(actual_file, "w") as f:
            json.dump(actual, f, indent=2)
        lines.append("")
        lines.append(f"Actual output saved to: {actual_file}")
        lines.append(f"To diff: diff {fixture_dir / f'{fixture_name}.{format_type}'} {actual_file}")

    return "\n".join(lines)


def format_csv_failure_message(fixture_name, expected, actual, fixture_dir):
    """
    Format a helpful failure message for CSV comparison failures.
    Optionally saves the actual output for manual diffing.
    """
    expected_lines = expected.strip().split("\n")
    actual_lines = actual.strip().split("\n")

    lines = [f"CSV export mismatch for {fixture_name}"]
    lines.append(f"Expected lines: {len(expected_lines)}, Actual lines: {len(actual_lines)}")

    # Find first differing line
    for i, (exp, act) in enumerate(zip(expected_lines, actual_lines)):
        if exp != act:
            lines.append(f"First difference at line {i + 1}:")
            lines.append(f"  Expected: {exp}")
            lines.append(f"  Actual:   {act}")
            break

    # Save actual output if enabled
    if should_save_failing_output():
        actual_file = fixture_dir / f"{fixture_name}.actual.csv"
        with open(actual_file, "w") as f:
            f.write(actual)
        lines.append("")
        lines.append(f"Actual output saved to: {actual_file}")
        lines.append(f"To diff: diff {fixture_dir / f'{fixture_name}.csv'} {actual_file}")

    return "\n".join(lines)


def get_fixture_names():
    """
    Discover all fixture sets by finding *.raw.json files in subdirectories.
    Returns list of tuples: (fixture_base_name, has_soil_data).

    Fixtures in with_soil/ will have soil_id data compared.
    Fixtures in without_soil/ will ignore soil_id data in comparisons.
    """
    fixtures = []

    # Find fixtures in with_soil directory
    if WITH_SOIL_DIR.exists():
        for raw_file in WITH_SOIL_DIR.glob("*.raw.json"):
            name = raw_file.stem.replace(".raw", "")
            fixtures.append((name, True))

    # Find fixtures in without_soil directory
    if WITHOUT_SOIL_DIR.exists():
        for raw_file in WITHOUT_SOIL_DIR.glob("*.raw.json"):
            name = raw_file.stem.replace(".raw", "")
            fixtures.append((name, False))

    return fixtures


def get_fixture_dir(has_soil):
    """Return the appropriate fixtures directory based on soil flag."""
    return WITH_SOIL_DIR if has_soil else WITHOUT_SOIL_DIR


def get_export_url(sites, owner, format_ext):
    """
    Create export token and return URL for exporting the given sites.

    Args:
        sites: List of Site instances
        owner: User who owns the export
        format_ext: File extension (json, csv, html)

    Returns:
        URL string for the export endpoint, or None if not supported
    """
    if len(sites) == 1:
        site = sites[0]
        token = ExportToken.create_token("SITE", str(site.id), str(owner.id))
        return f"/export/token/site/{token.token}/test.{format_ext}"
    else:
        project = sites[0].project
        if project:
            token = ExportToken.create_token("PROJECT", str(project.id), str(owner.id))
            return f"/export/token/project/{token.token}/test.{format_ext}"
    return None


def normalize_json_for_comparison(data, ignore_fields=None, parent_key=None, include_soil=True):
    """
    Normalize JSON data for comparison by removing fields that may legitimately differ.

    Args:
        data: Dict or list to normalize
        ignore_fields: Set of field names to remove (default: IGNORE_JSON_FIELDS)
        parent_key: Key of parent object (used to make context-sensitive decisions)
        include_soil: If False, also ignore soil_id field

    Returns:
        Normalized copy of the data
    """
    if ignore_fields is None:
        ignore_fields = IGNORE_JSON_FIELDS.copy()
        if not include_soil:
            ignore_fields.add("soil_id")

    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            if k in ignore_fields:
                continue
            # Skip IDs for notes and authors (they get regenerated)
            # but keep IDs for sites and projects (they're preserved from input)
            if k == "id" and parent_key in ("notes", "author"):
                continue
            result[k] = normalize_json_for_comparison(v, ignore_fields, parent_key=k, include_soil=include_soil)
        return result
    elif isinstance(data, list):
        return [normalize_json_for_comparison(item, ignore_fields, parent_key=parent_key, include_soil=include_soil) for item in data]
    return data


def normalize_csv_for_comparison(csv_content, ignore_columns=None, include_soil=True):
    """
    Normalize CSV content for comparison.

    Args:
        csv_content: CSV string
        ignore_columns: Set of column names to ignore (default: IGNORE_CSV_COLUMNS)
        include_soil: If False, also ignore soil-related columns

    Returns:
        Normalized CSV string with rows sorted by Site ID for stable comparison.
    """
    if csv_content.startswith('\ufeff'):
        csv_content = csv_content[1:]

    if ignore_columns is None:
        ignore_columns = IGNORE_CSV_COLUMNS.copy()
        if not include_soil:
            ignore_columns.update(SOIL_CSV_COLUMNS)

    lines = csv_content.strip().split("\n")
    if not lines:
        return ""

    # Use csv module for proper parsing of quoted fields
    reader = csv.reader(io.StringIO(csv_content))
    rows = list(reader)
    if not rows:
        return ""

    # Parse header to find column indices to keep
    header = rows[0]
    keep_indices = [i for i, col in enumerate(header) if col not in ignore_columns]

    # Find Site ID column index for sorting (after filtering)
    filtered_header = [header[i] for i in keep_indices if i < len(header)]
    site_id_col = None
    for i, col in enumerate(filtered_header):
        if col == "Site ID":
            site_id_col = i
            break

    # Filter columns
    result_rows = []
    for row in rows:
        filtered = [row[i] for i in keep_indices if i < len(row)]
        result_rows.append(filtered)

    # Sort data rows by Site ID (keep header at top)
    if len(result_rows) > 1 and site_id_col is not None:
        header_row = result_rows[0]
        data_rows = result_rows[1:]
        data_rows.sort(key=lambda r: r[site_id_col] if site_id_col < len(r) else "")
        result_rows = [header_row] + data_rows

    # Write back to CSV string
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerows(result_rows)
    return output.getvalue().strip()


class TestExportFixtures:
    """
    Parameterized tests that run against all fixture files.

    Add new test cases by adding files to the appropriate fixtures subdirectory:
        with_soil/     - Fixtures that should have soil_id data compared
        without_soil/  - Fixtures that should ignore soil_id data

    Each fixture needs:
        - mytest.raw.json (required - raw input data)
        - mytest.json (optional - expected JSON output)
        - mytest.csv (optional - expected CSV output)
    """

    @pytest.fixture
    def setup_fixture_data(self, request):
        """Load fixture data into the database and return site info."""
        fixture_name, has_soil = request.param
        fixture_dir = get_fixture_dir(has_soil)
        raw_file = fixture_dir / f"{fixture_name}.raw.json"

        owner = create_user_for_fixtures(email=f"{fixture_name}-owner@test.com")
        sites = load_sites_from_fixture(raw_file.name, owner, fixture_dir)

        return {
            "fixture_name": fixture_name,
            "has_soil": has_soil,
            "fixture_dir": fixture_dir,
            "owner": owner,
            "sites": sites,
        }

    @pytest.mark.parametrize(
        "setup_fixture_data",
        get_fixture_names(),
        indirect=True,
    )
    def test_export_json_matches_expected(self, client, setup_fixture_data):
        """Test that JSON export matches expected output file."""
        fixture_name = setup_fixture_data["fixture_name"]
        has_soil = setup_fixture_data["has_soil"]
        fixture_dir = setup_fixture_data["fixture_dir"]
        owner = setup_fixture_data["owner"]
        sites = setup_fixture_data["sites"]

        expected_file = fixture_dir / f"{fixture_name}.json"
        if not expected_file.exists():
            pytest.skip(f"No expected JSON file: {fixture_name}.json")

        with open(expected_file) as f:
            expected_data = json.load(f)

        url = get_export_url(sites, owner, "json")
        if url is None:
            pytest.skip("Multi-site fixtures without project not yet supported")

        response = client.get(url)
        assert response.status_code == 200, f"Export failed: {response.content}"

        actual_data = json.loads(response.content)

        # Normalize both for comparison (include_soil based on fixture directory)
        normalized_expected = normalize_json_for_comparison(expected_data, include_soil=has_soil)
        normalized_actual = normalize_json_for_comparison(actual_data, include_soil=has_soil)

        if normalized_actual != normalized_expected:
            pytest.fail(format_json_failure_message(
                fixture_name, normalized_expected, normalized_actual, fixture_dir
            ))

    @pytest.mark.parametrize(
        "setup_fixture_data",
        get_fixture_names(),
        indirect=True,
    )
    def test_export_csv_matches_expected(self, client, setup_fixture_data):
        """Test that CSV export matches expected output file."""
        fixture_name = setup_fixture_data["fixture_name"]
        has_soil = setup_fixture_data["has_soil"]
        fixture_dir = setup_fixture_data["fixture_dir"]
        owner = setup_fixture_data["owner"]
        sites = setup_fixture_data["sites"]

        expected_file = fixture_dir / f"{fixture_name}.csv"
        if not expected_file.exists():
            pytest.skip(f"No expected CSV file: {fixture_name}.csv")

        with open(expected_file) as f:
            expected_csv = f.read()

        url = get_export_url(sites, owner, "csv")
        if url is None:
            pytest.skip("Multi-site fixtures without project not yet supported")

        response = client.get(url)
        assert response.status_code == 200, f"Export failed: {response.content}"

        actual_csv = response.content.decode("utf-8")

        # Normalize both for comparison (include_soil based on fixture directory)
        normalized_expected = normalize_csv_for_comparison(expected_csv, include_soil=has_soil)
        normalized_actual = normalize_csv_for_comparison(actual_csv, include_soil=has_soil)

        if normalized_actual != normalized_expected:
            pytest.fail(format_csv_failure_message(
                fixture_name, normalized_expected, normalized_actual, fixture_dir
            ))
