#!/usr/bin/env python3
"""
Sync local CSV files to Google Sheets.

Requires:
  pip install gspread

Authentication (choose one):
  1. Service account: Set GOOGLE_APPLICATION_CREDENTIALS env var to path of JSON key file
     and share the spreadsheet with the service account email.
  2. OAuth: Run once to authenticate interactively, credentials cached in ~/.config/gspread/

Usage:
  ./sync_to_sheets.py staging    # Upload to staging sheet
  ./sync_to_sheets.py production # Upload to production sheet
  ./sync_to_sheets.py            # Defaults to staging
  ./sync_to_sheets.py --dry-run  # Show what would be uploaded without making changes
"""

import csv
import sys
from pathlib import Path

STAGING_SHEET_ID = "1D8HTWaUkHQJZ5CQKQ7FvHwA6BjPPdGIC4YSv_LfdCDY"
PRODUCTION_SHEET_ID = "1hNw0zCOuZ9td3ueWMXNZZahEagIDeGt8ryCreyNyqGc"

SCRIPT_DIR = Path(__file__).parent
CSV_FILES = ["objects.csv", "fields.csv", "enum_values.csv"]


def load_csv(filename: str) -> list[list[str]]:
    """Load CSV file as list of rows."""
    path = SCRIPT_DIR / filename
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        return list(reader)


def main():
    dry_run = "--dry-run" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    env = args[0] if args else "staging"

    if env in ("staging",):
        sheet_id = STAGING_SHEET_ID
        print("Target: staging sheet")
    elif env in ("production", "prod"):
        sheet_id = PRODUCTION_SHEET_ID
        print("Target: production sheet")
    else:
        print(f"Usage: {sys.argv[0]} [staging|production] [--dry-run]")
        sys.exit(1)

    if dry_run:
        print("DRY RUN - no changes will be made\n")
        for filename in CSV_FILES:
            data = load_csv(filename)
            sheet_name = filename.replace(".csv", "")
            print(f"Would upload {filename} ({len(data)} rows) to sheet '{sheet_name}'")
        return

    # Import gspread only when actually needed
    try:
        import gspread
    except ImportError:
        print("Error: gspread not installed. Run: pip install gspread")
        sys.exit(1)

    # Authenticate - tries service account first, then OAuth
    try:
        gc = gspread.service_account()
        print("Authenticated via service account")
    except Exception:
        try:
            gc = gspread.oauth()
            print("Authenticated via OAuth")
        except Exception as e:
            print(f"Authentication failed: {e}")
            print("\nTo set up authentication:")
            print("1. Service account: Set GOOGLE_APPLICATION_CREDENTIALS env var")
            print("2. OAuth: Run 'gspread' to set up interactively")
            sys.exit(1)

    # Open spreadsheet
    try:
        spreadsheet = gc.open_by_key(sheet_id)
    except gspread.SpreadsheetNotFound:
        print(f"Error: Cannot access spreadsheet {sheet_id}")
        print("Make sure the sheet is shared with your service account or user.")
        sys.exit(1)

    # Upload each CSV
    for filename in CSV_FILES:
        sheet_name = filename.replace(".csv", "")
        data = load_csv(filename)

        print(f"Uploading {filename} ({len(data)} rows) to '{sheet_name}'...")

        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            print(f"  Creating worksheet '{sheet_name}'...")
            worksheet = spreadsheet.add_worksheet(sheet_name, rows=len(data), cols=len(data[0]) if data else 1)

        # Clear and update
        worksheet.clear()
        if data:
            worksheet.update(data, "A1")

        print("  Done.")

    print("\nSync complete!")


if __name__ == "__main__":
    main()
