#!/usr/bin/env python3
"""
Validate export fixture files against documentation CSVs.

Fetches documentation CSVs from Google Sheets and validates that:
1. CSV fixture columns are all documented in fields.csv (csv_column)
2. JSON fixture fields are documented in fields.csv (json_name) and in correct hierarchy

Usage:
    ./validate_fixtures.py                  # Use staging sheets
    ./validate_fixtures.py production       # Use production sheets
    ./validate_fixtures.py local            # Use local CSV files
    ./validate_fixtures.py <spreadsheet_id> # Use custom sheet ID
"""

import csv
import json
import sys
import urllib.request
from io import StringIO
from pathlib import Path

STAGING_SHEET_ID = "1D8HTWaUkHQJZ5CQKQ7FvHwA6BjPPdGIC4YSv_LfdCDY"
PRODUCTION_SHEET_ID = "1hNw0zCOuZ9td3ueWMXNZZahEagIDeGt8ryCreyNyqGc"

DOCS_DIR = Path(__file__).parent
FIXTURES_DIR = DOCS_DIR.parent.parent.parent / "tests" / "export" / "fixtures"


def fetch_csv_from_sheets(sheet_id: str, sheet_name: str) -> list[dict]:
    """Fetch a CSV from Google Sheets and parse it."""
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    with urllib.request.urlopen(url) as response:
        content = response.read().decode("utf-8")
    reader = csv.DictReader(StringIO(content))
    return list(reader)


def load_local_csv(filename: str) -> list[dict]:
    """Load a CSV from the local docs directory."""
    path = DOCS_DIR / filename
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_documentation(sheet_id: str) -> tuple[list[dict], list[dict], list[dict]]:
    """Load all documentation CSVs from Google Sheets."""
    print(f"Fetching documentation from sheet {sheet_id}...")
    objects = fetch_csv_from_sheets(sheet_id, "objects")
    fields = fetch_csv_from_sheets(sheet_id, "fields")
    enum_values = fetch_csv_from_sheets(sheet_id, "enum_values")
    print(f"  Loaded {len(objects)} objects, {len(fields)} fields, {len(enum_values)} enum values")
    return objects, fields, enum_values


def load_documentation_local() -> tuple[list[dict], list[dict], list[dict]]:
    """Load all documentation CSVs from local files."""
    print("Loading documentation from local CSV files...")
    objects = load_local_csv("objects.csv")
    fields = load_local_csv("fields.csv")
    enum_values = load_local_csv("enum_values.csv")
    print(f"  Loaded {len(objects)} objects, {len(fields)} fields, {len(enum_values)} enum values")
    return objects, fields, enum_values


def build_field_index(fields: list[dict], objects: list[dict]) -> dict:
    """
    Build an index of documented fields.

    Returns dict with:
    - csv_columns: set of all csv_column values
    - json_fields: dict mapping object_name -> set of json_name values
    - field_types: dict mapping (object, json_name) -> type
    - object_names: set of all object names
    """
    csv_columns = set()
    json_fields = {}  # object_name -> set of json_names
    field_types = {}  # (object, json_name) -> type

    object_names = {obj["name"] for obj in objects}

    for field in fields:
        obj = field.get("object", "")
        json_name = field.get("json_name", "")
        csv_col = field.get("csv_column", "")
        field_type = field.get("type", "")

        if csv_col:
            csv_columns.add(csv_col)

        if json_name and obj:
            if obj not in json_fields:
                json_fields[obj] = set()
            json_fields[obj].add(json_name)
            field_types[(obj, json_name)] = field_type

    return {
        "csv_columns": csv_columns,
        "json_fields": json_fields,
        "field_types": field_types,
        "object_names": object_names,
    }


def validate_csv_fixture(csv_path: Path, field_index: dict) -> list[str]:
    """Validate a CSV fixture file against documentation."""
    errors = []
    documented_columns = field_index["csv_columns"]

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames or []

    for col in columns:
        if col not in documented_columns:
            errors.append(f"Undocumented CSV column: '{col}'")

    return errors


def normalize_path(path: str) -> str:
    """Normalize path by replacing array indices with []."""
    import re
    return re.sub(r'\[\d+\]', '[]', path)


def validate_json_object(
    obj: dict,
    object_type: str,
    path: str,
    field_index: dict,
    errors: set,  # Changed to set of tuples for deduplication
):
    """Recursively validate a JSON object against documentation."""
    json_fields = field_index["json_fields"]
    field_types = field_index["field_types"]
    object_names = field_index["object_names"]

    documented_fields = json_fields.get(object_type, set())

    for key, value in obj.items():
        current_path = f"{path}.{key}" if path else key
        normalized = normalize_path(current_path)

        if key not in documented_fields:
            # Store as tuple (field, object_type, normalized_path) for deduplication
            errors.add((key, object_type, normalized))
            continue

        # Get the expected type for this field
        expected_type = field_types.get((object_type, key), "")

        # Check if this field should contain a nested object
        is_array = expected_type.endswith("[]")
        base_type = expected_type[:-2] if is_array else expected_type

        if base_type in object_names:
            # This field should contain a nested object or array of objects
            if is_array and isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        validate_json_object(
                            item,
                            base_type,
                            f"{current_path}[{i}]",
                            field_index,
                            errors,
                        )
            elif isinstance(value, dict):
                validate_json_object(
                    value, base_type, current_path, field_index, errors
                )


def validate_json_fixture(json_path: Path, field_index: dict) -> list[str]:
    """Validate a JSON fixture file against documentation."""
    errors_set = set()  # Set of (field, object_type, normalized_path) tuples

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # The root should have a "sites" array
    if "sites" not in data:
        return ["JSON fixture missing 'sites' array at root"]

    for i, site in enumerate(data["sites"]):
        validate_json_object(site, "Site", f"sites[{i}]", field_index, errors_set)

    # Convert to list of error strings, sorted for consistent output
    errors = [
        f"Undocumented field '{field}' in {obj_type} (path: {path})"
        for field, obj_type, path in sorted(errors_set)
    ]
    return errors


def main():
    # Determine which source to use
    use_local = False
    sheet_id = STAGING_SHEET_ID

    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "production" or arg == "prod":
            sheet_id = PRODUCTION_SHEET_ID
        elif arg == "staging":
            sheet_id = STAGING_SHEET_ID
        elif arg == "local":
            use_local = True
        else:
            sheet_id = arg  # Assume it's a custom sheet ID

    # Load documentation
    if use_local:
        objects, fields, enum_values = load_documentation_local()
    else:
        objects, fields, enum_values = load_documentation(sheet_id)
    field_index = build_field_index(fields, objects)

    print(f"\nDocumented CSV columns: {len(field_index['csv_columns'])}")
    print(f"Documented JSON objects: {len(field_index['json_fields'])}")

    # Find fixture files
    csv_fixtures = sorted(FIXTURES_DIR.glob("*.csv"))
    json_fixtures = sorted(
        p for p in FIXTURES_DIR.glob("*.json") if not p.name.endswith(".raw.json")
    )

    print(f"\nFound {len(csv_fixtures)} CSV fixtures, {len(json_fixtures)} JSON fixtures")

    all_errors = []

    # Validate CSV fixtures
    print("\n=== Validating CSV fixtures ===")
    for csv_path in csv_fixtures:
        errors = validate_csv_fixture(csv_path, field_index)
        if errors:
            print(f"\n{csv_path.name}:")
            for err in errors:
                print(f"  - {err}")
            all_errors.extend(errors)
        else:
            print(f"  {csv_path.name}: OK")

    # Validate JSON fixtures
    print("\n=== Validating JSON fixtures ===")
    for json_path in json_fixtures:
        errors = validate_json_fixture(json_path, field_index)
        if errors:
            print(f"\n{json_path.name}:")
            for err in errors:
                print(f"  - {err}")
            all_errors.extend(errors)
        else:
            print(f"  {json_path.name}: OK")

    # Summary
    print(f"\n=== Summary ===")
    if all_errors:
        print(f"Found {len(all_errors)} validation errors")
        return 1
    else:
        print("All fixtures validated successfully!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
