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

import pytest

from apps.soil_id import munsell

# A tiny stand-in for the library's reference lookup so these tests don't depend
# on the downloaded LandPKS_munsell_rgb_lab.csv. Keyed by (hue_str, value, chroma).
FAKE_TABLE = {
    ("7.5YR", 5, 4): (50.0, 10.0, 20.0),
    ("10R", 4, 6): (40.0, 30.0, 15.0),
    ("2.5Y", 6, 2): (60.0, 5.0, 25.0),
    ("N", 5, 0): (52.0, 0.0, 0.0),
}


@pytest.fixture
def fake_table(monkeypatch):
    def fake_lookup(color_ref, munsell_ref, munsell):
        return FAKE_TABLE.get((munsell[0], int(munsell[1]), int(munsell[2])))

    monkeypatch.setattr(munsell, "_lib_munsell_to_lab", fake_lookup)


def test_string_to_lab_basic(fake_table):
    assert munsell.munsell_string_to_lab("7.5YR 5/4") == (50.0, 10.0, 20.0)
    assert munsell.munsell_string_to_lab("10R 4/6") == (40.0, 30.0, 15.0)
    assert munsell.munsell_string_to_lab("2.5Y 6/2") == (60.0, 5.0, 25.0)


def test_string_to_lab_neutral(fake_table):
    assert munsell.munsell_string_to_lab("N 5/") == (52.0, 0.0, 0.0)
    assert munsell.munsell_string_to_lab("N 5/0") == (52.0, 0.0, 0.0)
    # A non-neutral hue written with chroma 0 also resolves to neutral.
    assert munsell.munsell_string_to_lab("5YR 5/0") == (52.0, 0.0, 0.0)


def test_string_to_lab_is_lenient_about_whitespace_and_case(fake_table):
    assert munsell.munsell_string_to_lab("  7.5yr  5/4 ") == (50.0, 10.0, 20.0)


def test_string_to_lab_invalid_returns_none(fake_table):
    assert munsell.munsell_string_to_lab("") is None
    assert munsell.munsell_string_to_lab("not a color") is None
    assert munsell.munsell_string_to_lab("7.5ZZ 5/4") is None  # unknown hue family
    assert munsell.munsell_string_to_lab("7.5YR 9/9") is None  # not in table


def test_string_and_numeric_forms_agree(fake_table):
    # "7.5YR" is hue-family YR (index 1) * 10 + substep 7.5 = 17.5 on the 0-100 scale.
    assert munsell.munsell_string_to_lab("7.5YR 5/4") == munsell.munsell_to_lab(17.5, 5, 4)
    # The "10<family>" boundary: "10R" corresponds to numeric hue 10.
    assert munsell.munsell_string_to_lab("10R 4/6") == munsell.munsell_to_lab(10, 4, 6)


def test_decode_hue():
    # Shared 0-100 hue decoder used by munsell_to_lab and the export's
    # render_munsell_hue. substep is one of 2.5/5/7.5/10; family is the letters.
    assert munsell.decode_hue(17.5) == (7.5, "YR")
    assert munsell.decode_hue(22.5) == (2.5, "Y")
    # The "10X" boundary rolls into the top of the previous family's block.
    assert munsell.decode_hue(10) == (10, "R")
    assert munsell.decode_hue(20) == (10, "YR")
    # 0 and 100 are the same point (10RP).
    assert munsell.decode_hue(0) == (10, "RP")
    assert munsell.decode_hue(100) == (10, "RP")


def test_off_table_yields_none(monkeypatch):
    monkeypatch.setattr(munsell, "_lib_munsell_to_lab", lambda *args: None)
    assert munsell.munsell_string_to_lab("7.5YR 5/4") is None
    assert munsell.munsell_to_lab(17.5, 5, 4) is None
