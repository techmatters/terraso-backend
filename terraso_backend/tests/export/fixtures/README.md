# Export Test Fixtures

This directory contains fixture files for testing the export transformation pipeline.

## File Naming Convention

Each test case consists of up to three files with the same base name:

| File | Required | Description |
|------|----------|-------------|
| `<name>.raw.json` | Yes | Raw input data (from `?format=raw` export) |
| `<name>.json` | No | Expected JSON export output |
| `<name>.csv` | No | Expected CSV export output |

Tests are automatically discovered by finding `*.raw.json` files.

## Soil ID Caching

The `.raw.json` files include `soil_id` data captured at fixture creation time. During tests, this cached data is used instead of calling external soil APIs. This provides:

- **Fast tests**: No external API calls during test runs
- **Deterministic results**: Tests pass regardless of soil algorithm changes
- **Offline testing**: No network dependency

The cache is automatically populated when fixtures are loaded and cleared after each test.

## Creating New Fixtures

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

## Debugging Failed Tests

When a test fails, the output shows:
- Total number of differences
- First 20 differences with paths and values

To save the actual output for manual diffing:

```bash
docker compose run --rm -e SAVE_FAILING_OUTPUT=1 web pytest terraso_backend/tests/export/test_export_fixtures.py -k example
```

This creates `<name>.actual.json` or `<name>.actual.csv` files that you can diff against the expected files.

## What Gets Compared

### JSON Comparison

Ignored fields (may differ between test runs):
- `updatedAt`, `createdAt`, `deletedAt` (timestamps)
- `seen`, `profileImage` (dynamic fields)
- `project` (may differ for synthetic test projects)
- `soilMetadata`, `userRating`, `_selectedSoilName` (internal fields)
- `id` for notes and authors (regenerated on load)

### CSV Comparison

Ignored columns:
- `Last updated (UTC)`
- `Project name`, `Project ID`, `Project description`
- `Top match user rating`
