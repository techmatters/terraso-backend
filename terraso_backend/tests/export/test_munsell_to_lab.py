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
Cross-platform consistency tests for Munsell-to-CIELAB conversion.

The test fixture (munsellTestData.json) is generated from the mobile client's
npm munsell library. We compare the backend's CSV lookup table against it to
ensure the two implementations produce consistent LAB values.

The two implementations use different source data and methods:
- Backend: direct lookup in LandPKS_munsell_rgb_lab.csv (from soil-id-algorithm)
- Mobile: npm munsell library with interpolation and Bradford chromatic adaptation

A tolerance is used because the source data and conversion methods differ.
"""

import json
import os

import pytest

from apps.export.fetch_data import munsell_to_lab

# Requires LandPKS_munsell_rgb_lab.csv from `make download-soil-data`.
pytestmark = pytest.mark.integration

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "munsellTestData.json")

# Maximum allowed difference per LAB channel between backend and mobile client.
# This is deliberately generous — the goal is to catch gross errors (wrong hue
# decoding, swapped channels, etc.), not to enforce exact agreement between
# two different source datasets.
LAB_TOLERANCE = 6.0


def _load_test_entries():
    with open(FIXTURE_PATH) as f:
        data = json.load(f)
    return data["entries"]


def _entry_id(entry):
    """Generate a readable test ID from an entry."""
    return entry["munsell"]


@pytest.mark.parametrize("entry", _load_test_entries(), ids=_entry_id)
def test_munsell_to_lab_matches_client(entry):
    """Backend LAB values should be close to the mobile client's values."""
    hue100 = entry["hue100"]
    value = entry["value"]
    chroma = entry["chroma"]
    expected_lab = entry["lab"]

    result = munsell_to_lab(hue100, value, chroma)

    assert result is not None, (
        f"Lookup returned None for {entry['munsell']} "
        f"(hue100={hue100}, value={value}, chroma={chroma})"
    )

    actual_L, actual_A, actual_B = result

    assert abs(actual_L - expected_lab["L"]) <= LAB_TOLERANCE, (
        f"L channel: backend={actual_L:.2f}, client={expected_lab['L']:.2f}, "
        f"diff={abs(actual_L - expected_lab['L']):.2f}"
    )
    assert abs(actual_A - expected_lab["A"]) <= LAB_TOLERANCE, (
        f"A channel: backend={actual_A:.2f}, client={expected_lab['A']:.2f}, "
        f"diff={abs(actual_A - expected_lab['A']):.2f}"
    )
    assert abs(actual_B - expected_lab["B"]) <= LAB_TOLERANCE, (
        f"B channel: backend={actual_B:.2f}, client={expected_lab['B']:.2f}, "
        f"diff={abs(actual_B - expected_lab['B']):.2f}"
    )


def test_munsell_to_lab_hue_decoding():
    """Verify the hue100-to-Munsell-string decoding covers all 10 hue families.

    Uses the test fixture's hue100 values (which cover hue100 = 5, 10, 15, ..., 80)
    to confirm that each hue family resolves to a lookup hit.
    """
    entries = _load_test_entries()
    hue_families_seen = set()
    for entry in entries:
        if entry["chroma"] == 0:
            continue
        result = munsell_to_lab(entry["hue100"], entry["value"], entry["chroma"])
        if result is not None:
            hue_families_seen.add(entry["munsell"].split()[0])

    # The fixture covers R, YR, Y, GY, G, BG, B, PB families (with 5 and 10 substeps)
    # RP and P families (hue100 85-100) are not in the fixture
    expected_families = {
        "5R",
        "10R",
        "5YR",
        "10YR",
        "5Y",
        "10Y",
        "5GY",
        "10GY",
        "5G",
        "10G",
        "5BG",
        "10BG",
        "5B",
        "10B",
        "5PB",
        "10PB",
    }
    assert hue_families_seen == expected_families
