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

import csv
from datetime import datetime
from io import StringIO

from .transformers import flatten_site


def format_timestamp_for_csv(iso_timestamp):
    """Format ISO timestamp to YYYY-MM-DD HH:MM:SS UTC format for CSV"""
    if not iso_timestamp:
        return ""
    try:
        # Parse ISO format (e.g., 2025-11-11T17:42:15.065624+00:00 or +07:00)
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        # Convert to UTC if timezone-aware
        if dt.tzinfo is not None:
            from datetime import timezone

            dt = dt.astimezone(timezone.utc)
        # Format as YYYY-MM-DD HH:MM:SS (now in UTC)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, AttributeError):
        return iso_timestamp  # Return as-is if parsing fails


def sites_to_csv(sites):
    """Convert a list of sites to CSV format"""
    flattened_sites = []
    for site in sites:
        flattened_sites.extend(flatten_site(site))

    # Excel cell character limit (32,767 characters)
    EXCEL_CELL_LIMIT = 32767

    # CSV-specific transformations for Excel compatibility
    for row in flattened_sites:
        # Replace newlines with return symbol in Site notes field
        # U+23CE (⏎) is the "Return Symbol" - visually indicates line breaks without causing Excel parsing issues
        if "Site notes" in row and row["Site notes"]:
            notes = row["Site notes"]
            # Format timestamps in notes (format: "content | email | 2025-11-11T17:42:15.065624+00:00")
            # Split by semicolon (multiple notes) then by pipe (note fields)
            formatted_notes = []
            for note in notes.split(";"):
                if " | " in note:
                    parts = note.split(" | ")
                    if len(parts) == 3:
                        content, email, timestamp = parts
                        formatted_timestamp = format_timestamp_for_csv(timestamp.strip())
                        formatted_notes.append(f"{content} | {email} | {formatted_timestamp}")
                    else:
                        formatted_notes.append(note)
                else:
                    formatted_notes.append(note)
            notes = ";".join(formatted_notes)
            row["Site notes"] = notes.replace("\r\n", "\n").replace("\n", "\u23ce")

        # Format timestamps to YYYY-MM-DD HH:MM:SS UTC
        if "Last updated (UTC)" in row:
            row["Last updated (UTC)"] = format_timestamp_for_csv(row["Last updated (UTC)"])

        # Truncate any fields exceeding Excel's cell limit
        for field_name, value in row.items():
            if value and isinstance(value, str) and len(value) > EXCEL_CELL_LIMIT:
                # Truncate and add indicator
                row[field_name] = value[: EXCEL_CELL_LIMIT - 20] + " [TRUNCATED]"

    fieldnames = list(flattened_sites[0].keys()) if flattened_sites else []
    csv_buffer = StringIO()

    # Write UTF-8 BOM for Excel compatibility
    # U+FEFF (BOM) helps Excel recognize the file as UTF-8 encoded
    csv_buffer.write("\ufeff")

    writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
    writer.writeheader()
    writer.writerows(flattened_sites)
    csv_buffer.seek(0)
    return csv_buffer.getvalue()
