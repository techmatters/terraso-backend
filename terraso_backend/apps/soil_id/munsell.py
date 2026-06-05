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
"""Munsell -> CIELAB conversion for soil-ID input.

The reference table (``LandPKS_munsell_rgb_lab.csv``) and the actual lookup live
in the soil-id library (``soil_id.color.munsell_to_lab``), which loads the table
once at import. This module adds the app-specific layer on top: the 0-100
continuous hue encoding (``decode_hue``) and parsing of human Munsell strings,
then delegates the lookup to the library.

- ``munsell_to_lab(hue, value, chroma)`` — numeric form, where ``hue`` is the
  app's 0-100 continuous encoding (hue-family index * 10 + substep).
- ``munsell_string_to_lab("7.5YR 5/4")`` — the human-written string form.
"""

import re

from soil_id.color import munsell_to_lab as _lib_munsell_to_lab
from soil_id.config import MUNSELL_COLOR_REF, MUNSELL_REF

# Hue letter names in order, matching the app's colorHue (0-100) encoding.
_HUE_NAMES = ["R", "YR", "Y", "GY", "G", "BG", "B", "PB", "P", "RP"]

# Human Munsell strings: "<substep><FAMILY> <value>/<chroma>" (e.g. "7.5YR 5/4")
# and the neutral form "N <value>/" (chroma 0, e.g. "N 5/").
_NON_NEUTRAL_RE = re.compile(
    r"^\s*(?P<substep>\d+(?:\.\d+)?)\s*(?P<family>[A-Za-z]{1,2})\s+"
    r"(?P<value>\d+(?:\.\d+)?)\s*/\s*(?P<chroma>\d+(?:\.\d+)?)\s*$"
)
_NEUTRAL_RE = re.compile(r"^\s*[Nn]\s*(?P<value>\d+(?:\.\d+)?)\s*/\s*(?:\d+(?:\.\d+)?)?\s*$")


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


def _lookup(hue_str, value, chroma):
    """Look up ``(hue_str, value, chroma)`` in the library's reference table.

    Returns a plain-float ``(L, A, B)`` tuple, or None if it isn't in the table.
    """
    lab = _lib_munsell_to_lab(MUNSELL_COLOR_REF, MUNSELL_REF, [hue_str, value, chroma])
    return None if lab is None else tuple(float(component) for component in lab)


def munsell_to_lab(color_hue, color_value, color_chroma):
    """Convert app colorHue/colorValue/colorChroma to CIELAB.

    ``color_hue`` is the 0-100 continuous encoding. Returns (L, A, B), or None
    if the color isn't in the reference table.
    """
    value = round(color_value)
    chroma = round(color_chroma)
    if chroma == 0:
        return _lookup("N", value, 0)
    substep, family = decode_hue(color_hue)
    return _lookup(f"{substep:g}{family}", value, chroma)


def munsell_string_to_lab(munsell_string):
    """Convert a human Munsell string to CIELAB.

    Accepts ``"7.5YR 5/4"`` and the neutral form ``"N 5/"`` (case-insensitive).
    Returns (L, A, B), or None if the string can't be parsed or isn't in the
    reference table.
    """
    if not munsell_string:
        return None

    neutral = _NEUTRAL_RE.match(munsell_string)
    if neutral:
        return _lookup("N", round(float(neutral.group("value"))), 0)

    match = _NON_NEUTRAL_RE.match(munsell_string)
    if not match:
        return None

    value = round(float(match.group("value")))
    chroma = round(float(match.group("chroma")))
    if chroma == 0:
        return _lookup("N", value, 0)

    # The hue string matches the library's key format, e.g. "7.5YR" / "10R".
    hue_str = f"{float(match.group('substep')):g}{match.group('family').upper()}"
    return _lookup(hue_str, value, chroma)
