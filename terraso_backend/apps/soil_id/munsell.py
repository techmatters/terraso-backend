# Copyright © 2025 Technology Matters
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
"""Munsell <-> CIELAB conversion, backed by the soil-id lookup table.

The lookup table (``LandPKS_munsell_rgb_lab.csv``, a soil-id data asset) is
keyed by Munsell ``(hue_string, value, chroma)`` -> ``(L, A, B)``, where
``hue_string`` looks like ``"7.5YR"`` / ``"10R"`` and neutrals use ``"N"``.

Two entry points convert a Munsell color to LAB for the soil-ID algorithm:

- ``munsell_to_lab(hue, value, chroma)`` — numeric form, where ``hue`` is the
  app's 0-100 continuous encoding (hue-family index * 10 + substep).
- ``munsell_string_to_lab("7.5YR 5/4")`` — the human-written string form.
"""

import csv
import os
import re
import threading

import structlog

logger = structlog.get_logger(__name__)

_lock = threading.Lock()

# Munsell-to-CIELAB lookup table, loaded lazily from the soil-id data files.
# Keyed by (hue_string, value_int, chroma_int) -> (L, A, B).
_munsell_lab_table = None

# Hue letter names in order, matching the app's colorHue (0-100) encoding.
_HUE_NAMES = ["R", "YR", "Y", "GY", "G", "BG", "B", "PB", "P", "RP"]

# Human Munsell strings: "<substep><FAMILY> <value>/<chroma>" (e.g. "7.5YR 5/4")
# and the neutral form "N <value>/" (chroma 0, e.g. "N 5/").
_NON_NEUTRAL_RE = re.compile(
    r"^\s*(?P<substep>\d+(?:\.\d+)?)\s*(?P<family>[A-Za-z]{1,2})\s+"
    r"(?P<value>\d+(?:\.\d+)?)\s*/\s*(?P<chroma>\d+(?:\.\d+)?)\s*$"
)
_NEUTRAL_RE = re.compile(r"^\s*[Nn]\s*(?P<value>\d+(?:\.\d+)?)\s*/\s*(?:\d+(?:\.\d+)?)?\s*$")


def _load_munsell_lab_table():
    """Load the Munsell-to-CIELAB lookup table from the soil-id data files."""
    global _munsell_lab_table
    if _munsell_lab_table is not None:
        return _munsell_lab_table

    with _lock:
        # Double-check after acquiring lock.
        if _munsell_lab_table is not None:
            return _munsell_lab_table

        try:
            from soil_id.config import MUNSELL_RGB_LAB_PATH

            path = MUNSELL_RGB_LAB_PATH
        except ImportError:
            path = os.path.join(os.environ.get("DATA_PATH", "Data"), "LandPKS_munsell_rgb_lab.csv")

        table = {}
        try:
            with open(path, newline="") as f:
                for row in csv.DictReader(f):
                    hue = row["hue"]
                    value = int(row["value"])
                    chroma = int(row["chroma"])
                    table[(hue, value, chroma)] = (
                        float(row["cielab_l"]),
                        float(row["cielab_a"]),
                        float(row["cielab_b"]),
                    )
        except FileNotFoundError:
            logger.warning("Munsell-to-LAB lookup table not found", path=path)
            table = {}

        _munsell_lab_table = table
        return _munsell_lab_table


def decode_hue(color_hue):
    """Decode a 0-100 continuous Munsell hue into ``(substep, family)``.

    e.g. ``17.5 -> (7.5, "YR")``. ``substep`` is one of 2.5/5/7.5/10 and
    ``family`` is one of the ten Munsell hue families (R, YR, ..., RP). The
    0-100 scale is the ten families in order, ten units each; a ``10X`` hue
    rolls into the top of the previous family's block.
    """
    hue = 0 if color_hue == 100 else color_hue
    hue_index = int(hue // 10)
    substep = round((hue % 10) / 2.5)
    if substep == 0:
        hue_index = (hue_index + 9) % 10
        substep = 4
    return (substep * 5) / 2, _HUE_NAMES[hue_index]


def munsell_to_lab(color_hue, color_value, color_chroma):
    """Convert app colorHue/colorValue/colorChroma to CIELAB using the lookup table.

    ``color_hue`` is the 0-100 continuous encoding. Returns (L, A, B), or None
    if the color can't be looked up.
    """
    table = _load_munsell_lab_table()
    if not table:
        return None

    chroma = round(color_chroma)
    value = round(color_value)

    # Neutral color (chroma == 0).
    if chroma == 0:
        return table.get(("N", value, 0))

    substep, family = decode_hue(color_hue)
    hue_str = f"{substep:g}{family}"
    return table.get((hue_str, value, chroma))


def munsell_string_to_lab(munsell_string):
    """Convert a human Munsell string to CIELAB using the lookup table.

    Accepts ``"7.5YR 5/4"`` and the neutral form ``"N 5/"`` (case-insensitive).
    Returns (L, A, B), or None if the string can't be parsed or isn't in the
    lookup table.
    """
    if not munsell_string:
        return None
    table = _load_munsell_lab_table()
    if not table:
        return None

    neutral = _NEUTRAL_RE.match(munsell_string)
    if neutral:
        return table.get(("N", round(float(neutral.group("value"))), 0))

    match = _NON_NEUTRAL_RE.match(munsell_string)
    if not match:
        return None

    value = round(float(match.group("value")))
    chroma = round(float(match.group("chroma")))
    if chroma == 0:
        return table.get(("N", value, 0))

    # The table key matches munsell_to_lab's formatting, e.g. "7.5YR" / "10R".
    hue_str = f"{float(match.group('substep')):g}{match.group('family').upper()}"
    return table.get((hue_str, value, chroma))
