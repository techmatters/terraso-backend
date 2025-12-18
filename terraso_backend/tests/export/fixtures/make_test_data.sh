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

echo "Fetching transformed JSON..."
curl -s "${BASE_URL}.json?cached=20" | jq > "${OUTPUT_NAME}.json"

echo "Fetching CSV..."
curl -s "${BASE_URL}.csv?cached=20" > "${OUTPUT_NAME}.csv"

echo ""
echo "Generated files:"
ls -l "${OUTPUT_NAME}".*
