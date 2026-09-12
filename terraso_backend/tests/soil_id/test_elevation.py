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

"""Elevation input plumbing + Mapbox fallback (apps.soil_id.elevation)."""

import io
import types

import pytest
from django.conf import settings
from django.test import override_settings
from PIL import Image

from apps.soil_id import elevation as elevation_module
from apps.soil_id.elevation import _lonlat_to_tile, mapbox_elevation
from apps.soil_id.graphql.soil_id.resolvers import parse_rank_soils_input_data
from apps.soil_id.models.soil_id_cache import SoilIdCache


def _us_input(**overrides):
    """Minimal SoilIdInputData stand-in for the US branch of parse."""
    base = dict(slope=5.0, elevation=80.1, surface_cracks=None, depth_dependent_data=[])
    base.update(overrides)
    return types.SimpleNamespace(**base)


def _terrain_rgb_png(r, g, b, size=2):
    """A solid `size`x`size` Terrain-RGB PNG whose every pixel is (r, g, b)."""
    buf = io.BytesIO()
    Image.new("RGB", (size, size), (r, g, b)).save(buf, format="PNG")
    return buf.getvalue()


def _fake_tile_response(r, g, b):
    """Stand-in for a requests.Response carrying a Terrain-RGB tile."""
    return types.SimpleNamespace(
        content=_terrain_rgb_png(r, g, b),
        raise_for_status=lambda: None,
    )


def test_parse_maps_client_elevation_to_pelev():
    inputs = parse_rank_soils_input_data(_us_input(), SoilIdCache.DataRegion.US)
    assert inputs["pElev"] == 80.1
    assert inputs["pSlope"] == 5.0


def test_parse_pelev_none_when_client_omits_elevation():
    # None -> the resolver fills it from the server-side fallback.
    inputs = parse_rank_soils_input_data(_us_input(elevation=None), SoilIdCache.DataRegion.US)
    assert inputs["pElev"] is None


@override_settings(MAPBOX_ACCESS_TOKEN="")
def test_mapbox_elevation_without_token_is_none_and_makes_no_request(monkeypatch):
    # No token configured -> returns None *before* any network call. Patch
    # requests.get to blow up so a reordered token check can't slip through.
    def boom(*args, **kwargs):
        raise AssertionError("requests.get must not be called when no token is configured")

    monkeypatch.setattr(elevation_module.requests, "get", boom)
    assert mapbox_elevation(37.35, -122.09) is None


@override_settings(MAPBOX_ACCESS_TOKEN="ci-test-token")
def test_mapbox_elevation_decodes_terrain_rgb_pixel(monkeypatch):
    # Mapbox Terrain-RGB height encoding (meters):
    #   elevation = -10000 + (r * 65536 + g * 256 + b) * 0.1
    r, g, b = 1, 134, 160
    expected = -10000.0 + (r * 65536 + g * 256 + b) * 0.1

    seen = {}

    def fake_get(url, params=None, timeout=None):
        seen.update(url=url, params=params, timeout=timeout)
        return _fake_tile_response(r, g, b)

    monkeypatch.setattr(elevation_module.requests, "get", fake_get)
    monkeypatch.setattr(elevation_module, "_elev_cache", {})

    result = mapbox_elevation(37.35, -122.09)

    assert result == pytest.approx(expected)
    # Requests the Terrain-RGB tileset at the configured zoom, token as a query param.
    assert f"{elevation_module._TERRAIN_TILESET}/{elevation_module._TERRAIN_ZOOM}/" in seen["url"]
    assert seen["params"]["access_token"] == "ci-test-token"
    assert seen["timeout"] == 5


@override_settings(MAPBOX_ACCESS_TOKEN="ci-test-token")
def test_mapbox_elevation_caches_successful_lookup(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        return _fake_tile_response(1, 134, 160)

    monkeypatch.setattr(elevation_module.requests, "get", fake_get)
    monkeypatch.setattr(elevation_module, "_elev_cache", {})

    first = mapbox_elevation(37.35, -122.09)
    second = mapbox_elevation(37.35, -122.09)

    assert first == second
    assert len(calls) == 1  # second lookup served from cache, no repeat request


@pytest.mark.integration
def test_mapbox_elevation_live_smoke():
    """Hits the real Mapbox Terrain-RGB API. Skipped when no token is configured
    (e.g. fork PRs). Catches drift in the tile URL/height encoding that a mocked
    tile can't — a broken decode would land far outside the asserted window."""
    if not settings.MAPBOX_ACCESS_TOKEN:
        pytest.skip("MAPBOX_ACCESS_TOKEN not configured")

    # Downtown Denver, CO — ~1,600 m above sea level.
    elevation = mapbox_elevation(39.7392, -104.9903)
    assert elevation is not None
    assert 1000 < elevation < 2200


def test_lonlat_to_tile_centers_origin():
    # lon/lat (0, 0) sits at the center of the tile grid at any zoom.
    xf, yf = _lonlat_to_tile(0.0, 0.0, 1)
    assert xf == pytest.approx(1.0)
    assert yf == pytest.approx(1.0)
