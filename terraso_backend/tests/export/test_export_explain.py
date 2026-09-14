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

"""Unit tests for the ?explain=true export option (scoring-trace passthrough)."""

import json
from types import SimpleNamespace
from unittest import mock

from apps.export import fetch_data, views


def test_pop_explanation_extracts_and_removes():
    raw = {"soilId": {"soilMatches": {"matches": []}, "soilIdExplanation": {"v": 1}}}
    assert views._pop_explanation(raw) == {"v": 1}
    # removed from the source so it doesn't get flattened / null-stripped downstream
    assert "soilIdExplanation" not in raw["soilId"]
    assert views._pop_explanation(None) is None
    assert views._pop_explanation({"soilId": {}}) is None


def test_export_response_preserves_explanation_verbatim():
    """The trace is re-attached AFTER null-stripping, so its (meaningful) nulls
    survive while ordinary site nulls are still stripped."""
    trace = {
        "candidates": [
            {
                "name": "A",
                "score_components": [
                    {
                        "type": "horizon",
                        "segments": [
                            {
                                "slice_distance": None,
                                "features": [
                                    {
                                        "name": "rfv_intpl",
                                        "user": None,
                                        "candidate": 22.5,
                                        "norm_diff": None,
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }
    sites = [{"name": "Site 1", "id": "s1", "someNull": None, "_explanation": trace}]

    resp = views._export_sites_response(sites, output_format="json", filename="x", request=None)
    site = json.loads(resp.content)["sites"][0]

    assert "_explanation" not in site  # temp key never leaks
    assert "someNull" not in site  # ordinary nulls still stripped
    expl = site["soilIdExplanation"]
    seg = expl["candidates"][0]["score_components"][0]["segments"][0]
    assert seg["slice_distance"] is None  # would be gone if strip touched the trace
    assert seg["features"][0]["user"] is None
    assert seg["features"][0]["norm_diff"] is None
    assert seg["features"][0]["candidate"] == 22.5


def test_export_response_without_explanation_unchanged():
    sites = [{"name": "Site 1", "id": "s1", "keep": 1, "drop": None}]
    resp = views._export_sites_response(sites, output_format="json", filename="x", request=None)
    site = json.loads(resp.content)["sites"][0]
    assert site == {"name": "Site 1", "id": "s1", "keep": 1}
    assert "soilIdExplanation" not in site


def _site():
    return {
        "id": "s1",
        "latitude": 0.14594,
        "longitude": 35.87959,
        "soilData": {"surfaceCracksSelect": "NO_CRACKING", "depthDependentData": []},
    }


def test_fetch_soil_id_requests_explanation_when_asked():
    trace = {"version": "1", "region": "GLOBAL", "candidates": []}
    fake = SimpleNamespace(
        errors=None,
        data={
            "soilId": {
                "soilMatches": {"dataRegion": "GLOBAL", "matches": []},
                "soilIdExplanation": trace,
            }
        },
    )
    with (
        mock.patch.object(fetch_data, "get_visible_intervals", return_value=[]),
        mock.patch.object(fetch_data, "schema") as sch,
    ):
        sch.execute.return_value = fake
        result = fetch_data.fetch_soil_id(_site(), request=mock.MagicMock(), include_explain=True)

    gql = sch.execute.call_args.args[0]
    assert "soilIdExplanation(" in gql
    assert result["soilId"]["soilIdExplanation"] == trace


def test_fetch_soil_id_omits_explanation_by_default():
    fake = SimpleNamespace(
        errors=None, data={"soilId": {"soilMatches": {"dataRegion": "GLOBAL", "matches": []}}}
    )
    with (
        mock.patch.object(fetch_data, "get_visible_intervals", return_value=[]),
        mock.patch.object(fetch_data, "schema") as sch,
    ):
        sch.execute.return_value = fake
        fetch_data.fetch_soil_id(_site(), request=mock.MagicMock())

    assert "soilIdExplanation(" not in sch.execute.call_args.args[0]
