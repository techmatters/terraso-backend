# Export Test Fixtures

This directory contains fixture files for testing the export transformation pipeline.

## File Naming Convention

Each test case consists of up to three files with the same base name:

| File              | Required | Description                                |
| ----------------- | -------- | ------------------------------------------ |
| `<name>.raw.json` | Yes      | Raw input data (from `?format=raw` export) |
| `<name>.json`     | No       | Expected JSON export output                |
| `<name>.csv`      | No       | Expected CSV export output                 |

Tests are automatically discovered by finding `*.raw.json` files.

## Soil ID Caching

The `.raw.json` files include `soil_id` data captured at fixture creation time. During tests, this cached data is used instead of calling external soil APIs. This provides:

-   **Fast tests**: No external API calls during test runs
-   **Deterministic results**: Tests pass regardless of soil algorithm changes
-   **Offline testing**: No network dependency

The cache is automatically populated when fixtures are loaded and cleared after each test.

## Creating New Fixtures

### Caution

If you use staging or production to generate your test sites, and the export format changes, then when you generate new fixture data using the options below, the scripts will grab .csv and .json files from staging or production, which will not include the export format changes. This means you cannot easily create good .csv and .json files so github will complain that the fixture export tests have failed.

The simplest solution is to let it fail, deploy to staging, then regenerate the fixtures files, and commit again. ideally also push to staging again, but since all you changed were test files, this may not be necessary.

### Option 1: Using the helper script

```bash
./make_test_data.sh "http://localhost:8000/export/token/site/{token}/name"
```

This generates all three files automatically.

### Option 2: Manual creation

#### Step 1: Get the raw input data

Export from a real environment using the `?format=raw` query parameter:

```bash
curl "https://api.terraso.org/export/token/site/{token}/name.json?format=raw" | jq > name.raw.json
```

Or for a project:

```bash
curl "https://api.terraso.org/export/token/project/{token}/name.json?format=raw" | jq > name.raw.json
```

#### Step 2: Get the expected outputs

Export the normal (transformed) outputs:

```bash
# JSON output
curl "https://api.terraso.org/export/token/site/{token}/name.json" | jq > name.json

# CSV output
curl "https://api.terraso.org/export/token/site/{token}/name.csv" > name.csv
```

### Step 3: Run the tests

```bash
PATTERN="test_export_fixtures" make test_unit
```

## Limitations

### Multi-Site Fixtures and Pinned Notes

When a fixture contains multiple sites, the test framework creates a **synthetic project** to group them together (required for project-based export). This synthetic project can only have one `siteInstructions` (pinned note) value.

**This means fixtures cannot be created from exports where:**

-   Multiple sites come from **different projects**
-   Those projects have **different `siteInstructions`** values

The `make_test_data.sh` script automatically detects this case and will error out with an explanation.

**Safe fixture sources:**
| Source | Safe? | Reason |
|--------|-------|--------|
| Single project export | ✓ | All sites share same `siteInstructions` |
| Single site export | ✓ | No synthetic project needed |
| User's owned sites (no projects) | ✓ | No `siteInstructions` to conflict |
| User's all sites (multiple projects) | ⚠️ | Only if all projects have same (or no) `siteInstructions` |

## Debugging Failed Tests

When a test fails, the output shows:

-   Total number of differences
-   First 20 differences with paths and values

To save the actual output for manual diffing:

```bash
docker compose run --rm -e SAVE_FAILING_OUTPUT=1 web pytest terraso_backend/tests/export/test_export_fixtures.py -k example
```

This creates `<name>.actual.json` or `<name>.actual.csv` files that you can diff against the expected files.

## What Gets Compared

### JSON Comparison

Ignored fields (may differ between test runs):

-   `updatedAt`, `createdAt`, `deletedAt` (timestamps)
-   `seen`, `profileImage` (dynamic fields)
-   `project` (may differ for synthetic test projects)
-   `soilMetadata`, `userRating`, `_selectedSoilName` (internal fields)
-   `id` for notes and authors (regenerated on load)

### CSV Comparison

Ignored columns:

-   `Last updated (UTC)`
-   `Project name`, `Project ID`, `Project description`
-   `Top match user rating`
