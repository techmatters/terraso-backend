#!/bin/bash
# Generate test fixture files from an export URL
#
# Usage: ./make_test_data.sh <url>
#
# Arguments:
#   url - The export URL (can end in .html, .json, .csv, or no extension)
#         e.g., http://localhost:8000/export/token/site/abc123/my_site.html
#         e.g., http://localhost:8000/export/token/site/abc123/my_site
#
# The output name is derived from the last path segment of the URL.
# This will generate:
#   - <name>.raw.json  (raw format)
#   - <name>.json      (transformed format)
#   - <name>.csv       (CSV format)

set -e

if [ $# -ne 1 ]; then
    echo "Usage: $0 <url>"
    echo ""
    echo "Example:"
    echo "  $0 http://localhost:8000/export/token/site/abc123/my_site.html"
    exit 1
fi

INPUT_URL="$1"

# Strip any extension (.html, .json, .csv) from the URL
BASE_URL="${INPUT_URL%.html}"
BASE_URL="${BASE_URL%.json}"
BASE_URL="${BASE_URL%.csv}"

# Extract the output name from the last path segment
OUTPUT_NAME=$(basename "$BASE_URL")

echo "Fetching raw JSON..."
curl -s "${BASE_URL}.json?format=raw&cached=20" | jq > "${OUTPUT_NAME}.raw.json"

# Check for multi-site fixtures with different siteInstructions (would fail in tests)
SITE_COUNT=$(jq '.sites | length' "${OUTPUT_NAME}.raw.json")
if [ "$SITE_COUNT" -gt 1 ]; then
    # Get unique siteInstructions values (excluding null)
    UNIQUE_INSTRUCTIONS=$(jq -r '[.sites[].project.siteInstructions | select(. != null)] | unique | length' "${OUTPUT_NAME}.raw.json")
    if [ "$UNIQUE_INSTRUCTIONS" -gt 1 ]; then
        echo ""
        echo "ERROR: Multi-site fixture has sites from different projects with different siteInstructions."
        echo "       This will cause test failures because the test framework uses a synthetic project"
        echo "       that can only have one siteInstructions value."
        echo ""
        echo "       Consider exporting sites from a single project instead, or individual sites."
        rm -f "${OUTPUT_NAME}.raw.json"
        exit 1
    fi
fi

echo "Fetching transformed JSON..."
curl -s "${BASE_URL}.json?cached=20" | jq > "${OUTPUT_NAME}.json"

echo "Fetching CSV..."
curl -s "${BASE_URL}.csv?cached=20" > "${OUTPUT_NAME}.csv"

echo ""
echo "Generated files:"
ls -l "${OUTPUT_NAME}".*
