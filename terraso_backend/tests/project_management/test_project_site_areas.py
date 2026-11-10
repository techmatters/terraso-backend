# Copyright © 2026 Technology Matters
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
from io import StringIO

import pytest
from django.core.management import call_command
from mixer.backend.django import mixer
from shapely.geometry import box

from apps.core.models import User
from apps.project_management.management.commands.project_site_areas import (
    convex_hull,
    geodesic_area_ha,
    unique_area_ha,
    unwrap_antimeridian,
)
from apps.project_management.models import Project, Site

# 0.01° x 0.01° at the equator is about 1113.2 m x 1105.7 m on WGS84.
SQUARE = [(0, 0), (0.01, 0), (0.01, 0.01), (0, 0.01)]
SQUARE_HA = 123.09
BIG_SQUARE = [(0, 0), (0.02, 0), (0.02, 0.02), (0, 0.02)]


def hull_area_ha(coords):
    return geodesic_area_ha(convex_hull(coords))


def shifted(coords, dlon):
    return [(lon + dlon, lat) for lon, lat in coords]


# ---------------------------------------------------------------------------
# Per-project area: convex_hull() / geodesic_area_ha() / unwrap_antimeridian()
# ---------------------------------------------------------------------------


def test_area_of_square():
    assert hull_area_ha(SQUARE) == pytest.approx(SQUARE_HA, rel=1e-3)


def test_interior_points_and_order_do_not_change_area():
    coords = [(0.005, 0.005), *reversed(SQUARE), (0.002, 0.008)]
    assert hull_area_ha(coords) == pytest.approx(SQUARE_HA, rel=1e-3)


@pytest.mark.parametrize(
    "coords",
    [
        [],
        [(0, 0)],
        [(0, 0), (1, 1)],
        [(0, 0), (0, 0), (1, 1)],
        [(0, 0), (1, 1), (2, 2)],
    ],
    ids=["no sites", "one site", "two sites", "duplicate sites", "collinear sites"],
)
def test_area_is_zero_when_sites_enclose_nothing(coords):
    assert hull_area_ha(coords) == 0.0


def test_square_straddling_antimeridian_has_same_area_as_at_zero():
    # Interior points on both sides of the line would become hull vertices if the cluster were hulled as a globe-spanning band.
    coords = [
        (179.995, 0),
        (-179.995, 0),
        (-179.995, 0.01),
        (179.995, 0.01),
        (179.999, 0.005),
        (-179.999, 0.005),
    ]
    assert hull_area_ha(coords) == pytest.approx(SQUARE_HA, rel=1e-3)


def test_area_excludes_holes():
    ring = box(0, 0, 0.03, 0.03).difference(box(0.01, 0.01, 0.02, 0.02))
    assert geodesic_area_ha(ring) == pytest.approx(8 * SQUARE_HA, rel=1e-3)


def test_unwrap_leaves_ordinary_coords_unchanged():
    coords = [(-70.4, 43.4), (-70.3, 43.5), (-70.35, 43.45)]
    assert unwrap_antimeridian(coords) == coords


def test_unwrap_makes_cluster_straddling_antimeridian_continuous():
    (east_lon, _), (west_lon, _) = unwrap_antimeridian([(179.9, 0), (-179.9, 0)])
    assert east_lon == 179.9
    assert west_lon == pytest.approx(180.1)


# ---------------------------------------------------------------------------
# unique_area_ha()
# ---------------------------------------------------------------------------


def test_unique_area_counts_overlap_once():
    hulls = [convex_hull(SQUARE), convex_hull(shifted(SQUARE, 0.005))]
    assert unique_area_ha(hulls) == pytest.approx(1.5 * SQUARE_HA, rel=1e-3)


def test_unique_area_of_disjoint_hulls_is_their_sum():
    hulls = [convex_hull(SQUARE), convex_hull(shifted(SQUARE, 1))]
    assert unique_area_ha(hulls) == pytest.approx(sum(geodesic_area_ha(h) for h in hulls))


def test_unique_area_excludes_hole_enclosed_by_hulls():
    # Four strips framing an empty 0.01° square in the middle.
    strips = [
        box(0, 0, 0.03, 0.01),
        box(0, 0.02, 0.03, 0.03),
        box(0, 0, 0.01, 0.03),
        box(0.02, 0, 0.03, 0.03),
    ]
    assert unique_area_ha(strips) == pytest.approx(8 * SQUARE_HA, rel=1e-3)


def test_unique_area_merges_hulls_across_antimeridian():
    # One square straddles the line (179.995 to -179.995); the other lies just west of it (-179.999 to -179.989), overlapping by 0.004°.
    straddling = convex_hull([(179.995, 0), (-179.995, 0), (-179.995, 0.01), (179.995, 0.01)])
    west_only = convex_hull(shifted(SQUARE, -179.999))
    assert unique_area_ha([straddling, west_only]) == pytest.approx(1.6 * SQUARE_HA, rel=1e-3)


def test_unique_area_of_overlapping_continent_sized_hulls_is_between_largest_and_sum():
    # Without extra vertices, the merged outline bulges differently on the globe than the first hull and measures less than it.
    hulls = [
        convex_hull([(-90, 5), (37, 41), (20, 5)]),
        convex_hull([(-72, 1), (38, 42), (-60, 30)]),
    ]
    areas = [geodesic_area_ha(hull) for hull in hulls]
    assert max(areas) <= unique_area_ha(hulls) <= sum(areas)


def test_unique_area_ignores_hulls_without_area():
    assert unique_area_ha([]) == 0.0
    assert unique_area_ha([convex_hull([]), convex_hull([(0, 0), (1, 1)])]) == 0.0


# ---------------------------------------------------------------------------
# project_site_areas command
# ---------------------------------------------------------------------------


def _project_with_sites(name, coords, archived=False):
    project = mixer.blend(Project, name=name, archived=archived)
    for lon, lat in coords:
        mixer.blend(Site, project=project, longitude=lon, latitude=lat, archived=False)
    return project


def _run_command(**kwargs):
    out = StringIO()
    call_command("project_site_areas", stdout=out, **kwargs)
    return out.getvalue()


def _parse_stdout(output):
    csv_text, totals = output.split("\n\n")
    return list(csv.DictReader(StringIO(csv_text))), totals.splitlines()


def _totals(project_area_sum, unique_area):
    return [
        f"Sum of project areas (ha): {project_area_sum:.2f}",
        f"Unique area covered (ha): {unique_area:.2f}",
    ]


@pytest.mark.django_db
def test_command_lists_projects_largest_first_with_totals():
    # Small lies inside Big, so the unique area is just Big's.
    big = _project_with_sites("Big", BIG_SQUARE)
    small = _project_with_sites("Small", SQUARE)
    empty = _project_with_sites("Empty", [])

    rows, totals = _parse_stdout(_run_command())

    assert [row["project_id"] for row in rows] == [str(big.id), str(small.id), str(empty.id)]
    assert [row["site_count"] for row in rows] == ["4", "4", "0"]
    assert float(rows[1]["area_ha"]) == pytest.approx(SQUARE_HA, rel=1e-3)
    assert rows[2]["area_ha"] == "0.00"
    big_ha = hull_area_ha(BIG_SQUARE)
    assert totals == _totals(big_ha + hull_area_ha(SQUARE), big_ha)


@pytest.mark.django_db
def test_command_excludes_deleted_and_archived_data():
    project = _project_with_sites("Live", SQUARE)
    mixer.blend(Site, project=project, longitude=5, latitude=5, archived=True)
    mixer.blend(Site, project=project, longitude=-5, latitude=-5, archived=False).delete()
    _project_with_sites("Archived", SQUARE, archived=True)
    _project_with_sites("Deleted", SQUARE).delete()
    mixer.blend(Site, owner=mixer.blend(User), project=None, longitude=5, latitude=-5)

    rows, _ = _parse_stdout(_run_command())

    assert [row["project_name"] for row in rows] == ["Live"]
    assert rows[0]["site_count"] == "4"
    assert float(rows[0]["area_ha"]) == pytest.approx(SQUARE_HA, rel=1e-3)


@pytest.mark.django_db
def test_command_writes_csv_to_output_file(tmp_path):
    project = _project_with_sites("Small", SQUARE)
    path = tmp_path / "areas.csv"

    output = _run_command(output=str(path))

    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    assert [row["project_id"] for row in rows] == [str(project.id)]
    square_ha = hull_area_ha(SQUARE)
    assert output.splitlines() == [f"Wrote 1 projects to {path}", *_totals(square_ha, square_ha)]
