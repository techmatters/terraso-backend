# Export Documentation System

This folder contains the documentation system for LandPKS export formats (CSV and JSON).

## Overview

Documentation is maintained in **Google Sheets** (the master source) and rendered dynamically on WordPress pages using JavaScript.

### Google Sheets

| Environment | Sheet ID |
|-------------|----------|
| Staging | `1D8HTWaUkHQJZ5CQKQ7FvHwA6BjPPdGIC4YSv_LfdCDY` |
| Production | `1hNw0zCOuZ9td3ueWMXNZZahEagIDeGt8ryCreyNyqGc` |

Each spreadsheet has three tabs:

- **objects** - Object/entity definitions (name, label, description)
- **fields** - Field definitions (object, json_name, csv_column, csv_section, type, description)
- **enum_values** - Enum value definitions (enum, value, label, description)

## Files

### Sync Scripts

- `sync_from_sheets.sh` - Download CSVs from Google Sheets to local files
  ```bash
  ./sync_from_sheets.sh staging    # Download from staging
  ./sync_from_sheets.sh production # Download from production
  ```

- `sync_to_sheets.py` - Upload local CSVs to Google Sheets (requires `gspread` and auth setup)
  ```bash
  ./sync_to_sheets.py staging      # Upload to staging
  ./sync_to_sheets.py --dry-run    # Preview without changes
  ```

### HTML Pages (WordPress Embeds)

These are embedded in WordPress pages and load documentation dynamically:

- `csv_dynamic_wp.html` - CSV format documentation
- `json_dynamic_tree_wp.html` - JSON structure tree view
- `json_dynamic_fields_wp.html` - JSON field reference tables
- `json_dynamic_hierarchy_wp.html` - JSON nested hierarchy visualization

### JavaScript & CSS

- `export_docs.js` - Shared JavaScript for parsing CSVs and rendering documentation
- `export_docs_wp.css` - Styles for WordPress-embedded documentation

### Validation

- `validate_fixtures.py` - Validate test fixtures against documentation
  ```bash
  ./validate_fixtures.py local      # Validate against local CSVs
  ./validate_fixtures.py staging    # Validate against staging sheet
  ./validate_fixtures.py production # Validate against production sheet
  ```

## Workflow

### Updating Documentation

1. Edit the **staging** Google Sheet directly
2. Preview changes on staging WordPress pages
3. When ready for production, copy changes to the **production** sheet

### Validating Changes

1. Download CSVs locally: `./sync_from_sheets.sh staging`
2. Run validation: `./validate_fixtures.py local`
3. Fix any undocumented fields or mismatches

### Adding New Fields

1. Add the field to the **fields** tab in Google Sheets
2. If it's a new object type, add to **objects** tab
3. If it's an enum type, add values to **enum_values** tab
4. Run `validate_fixtures.py` to verify

## CSV Schema Reference

### objects.csv

| Column | Description |
|--------|-------------|
| name | Object name (e.g., "Site", "Soil Observations") |
| label | Display label for sections (optional) |
| description | Object description |

### fields.csv

| Column | Description |
|--------|-------------|
| object | Parent object name |
| json_name | Field name in JSON export |
| csv_column | Column header in CSV export |
| csv_section | CSV grouping ("CSV Site" or "CSV Depth") |
| type | Data type (string, number, boolean, datetime, or object/enum name) |
| description | Field description |

### enum_values.csv

| Column | Description |
|--------|-------------|
| enum | Enum type name (matches field type) |
| value | Value in JSON export |
| label | Display label in CSV export |
| description | Optional description (shown in JSON docs if present) |
