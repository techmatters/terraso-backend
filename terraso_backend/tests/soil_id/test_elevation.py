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

import types

import pytest
from django.test import override_settings

from apps.soil_id.elevation import _lonlat_to_tile, mapbox_elevation
from apps.soil_id.graphql.soil_id.resolvers import parse_rank_soils_input_data
from apps.soil_id.models.soil_id_cache import SoilIdCache


def _us_input(**overrides):
    """Minimal SoilIdInputData stand-in for the US branch of parse."""
    base = dict(slope=5.0, elevation=80.1, surface_cracks=None, depth_dependent_data=[])
    base.update(overrides)
    return types.SimpleNamespace(**base)


def test_parse_maps_client_elevation_to_pelev():
    inputs = parse_rank_soils_input_data(_us_input(), SoilIdCache.DataRegion.US)
    assert inputs["pElev"] == 80.1
    assert inputs["pSlope"] == 5.0


def test_parse_pelev_none_when_client_omits_elevation():
    # None -> the resolver fills it from the server-side fallback.
    inputs = parse_rank_soils_input_data(_us_input(elevation=None), SoilIdCache.DataRegion.US)
    assert inputs["pElev"] is None


@override_settings(MAPBOX_ACCESS_TOKEN="")
def test_mapbox_elevation_without_token_is_none_and_makes_no_request():
    # No token configured -> returns None without any network call.
    assert mapbox_elevation(37.35, -122.09) is None


def test_lonlat_to_tile_centers_origin():
    # lon/lat (0, 0) sits at the center of the tile grid at any zoom.
    xf, yf = _lonlat_to_tile(0.0, 0.0, 1)
    assert xf == pytest.approx(1.0)
    assert yf == pytest.approx(1.0)
