#!/bin/bash
# Sync CSV files from Google Sheets to local files
#
# Usage:
#   ./sync_from_sheets.sh staging    # Download from staging sheet
#   ./sync_from_sheets.sh production # Download from production sheet
#   ./sync_from_sheets.sh            # Defaults to staging

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

STAGING_SHEET_ID="1D8HTWaUkHQJZ5CQKQ7FvHwA6BjPPdGIC4YSv_LfdCDY"
PRODUCTION_SHEET_ID="1hNw0zCOuZ9td3ueWMXNZZahEagIDeGt8ryCreyNyqGc"

ENV="${1:-staging}"

case "$ENV" in
  staging)
    SHEET_ID="$STAGING_SHEET_ID"
    echo "Syncing from staging sheet..."
    ;;
  production|prod)
    SHEET_ID="$PRODUCTION_SHEET_ID"
    echo "Syncing from production sheet..."
    ;;
  *)
    echo "Usage: $0 [staging|production]"
    exit 1
    ;;
esac

BASE_URL="https://docs.google.com/spreadsheets/d/${SHEET_ID}/gviz/tq?tqx=out:csv&sheet="

for sheet in objects fields enum_values; do
  echo "  Downloading ${sheet}.csv..."
  curl -sL "${BASE_URL}${sheet}" -o "${sheet}.csv"
done

echo "Done."
