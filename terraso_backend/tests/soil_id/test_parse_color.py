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

from types import SimpleNamespace

from apps.soil_id.graphql.soil_id import resolvers


def _depth(**overrides):
    fields = {"color_LAB": None, "color_munsell": None, "color_munsell_numeric": None}
    fields.update(overrides)
    return SimpleNamespace(**fields)


def test_no_color_returns_none():
    assert resolvers.parse_color(_depth()) is None


def test_lab_is_used_directly():
    depth = _depth(color_LAB=SimpleNamespace(L=1.0, A=2.0, B=3.0))
    assert resolvers.parse_color(depth) == [1.0, 2.0, 3.0]


def test_lab_takes_precedence_over_munsell(monkeypatch):
    monkeypatch.setattr(resolvers, "munsell_string_to_lab", lambda s: (9.0, 9.0, 9.0))
    depth = _depth(
        color_LAB=SimpleNamespace(L=1.0, A=2.0, B=3.0),
        color_munsell="7.5YR 5/4",
    )
    assert resolvers.parse_color(depth) == [1.0, 2.0, 3.0]


def test_munsell_string_is_converted(monkeypatch):
    monkeypatch.setattr(resolvers, "munsell_string_to_lab", lambda s: (10.0, 20.0, 30.0))
    assert resolvers.parse_color(_depth(color_munsell="7.5YR 5/4")) == [10.0, 20.0, 30.0]


def test_munsell_string_takes_precedence_over_numeric(monkeypatch):
    monkeypatch.setattr(resolvers, "munsell_string_to_lab", lambda s: (7.0, 7.0, 7.0))
    monkeypatch.setattr(resolvers, "munsell_to_lab", lambda h, v, c: (1.0, 1.0, 1.0))
    depth = _depth(
        color_munsell="7.5YR 5/4",
        color_munsell_numeric=SimpleNamespace(hue=17.5, value=5, chroma=4),
    )
    assert resolvers.parse_color(depth) == [7.0, 7.0, 7.0]


def test_munsell_numeric_is_converted(monkeypatch):
    monkeypatch.setattr(resolvers, "munsell_to_lab", lambda h, v, c: (1.0, 2.0, 3.0))
    depth = _depth(color_munsell_numeric=SimpleNamespace(hue=17.5, value=5, chroma=4))
    assert resolvers.parse_color(depth) == [1.0, 2.0, 3.0]


def test_unconvertible_munsell_string_is_ignored(monkeypatch):
    # An out-of-gamut color is dropped (no color for that depth), not an error.
    monkeypatch.setattr(resolvers, "munsell_string_to_lab", lambda s: None)
    assert resolvers.parse_color(_depth(color_munsell="bogus")) is None


def test_unconvertible_munsell_numeric_is_ignored(monkeypatch):
    monkeypatch.setattr(resolvers, "munsell_to_lab", lambda h, v, c: None)
    depth = _depth(color_munsell_numeric=SimpleNamespace(hue=999, value=5, chroma=4))
    assert resolvers.parse_color(depth) is None
