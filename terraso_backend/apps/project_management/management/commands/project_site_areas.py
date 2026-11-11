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

"""Report the area covered by each project's sites, as CSV.

A project's area is the convex hull around its sites (deleted and archived ones excluded), measured on the WGS84 ellipsoid. Projects with fewer than 3 distinct, non-collinear sites get 0. Sites with impossible coordinates are left out, with a warning on stderr. The output ends with two totals: the sum of all project areas (overlapping projects counted more than once) and the unique area covered (overlaps counted once).

Usage:
    python manage.py project_site_areas                     # CSV to stdout
    python manage.py project_site_areas --output areas.csv  # CSV to a file
"""

import csv
import math
from collections import defaultdict
from contextlib import contextmanager
from itertools import pairwise

from django.core.management.base import BaseCommand
from django.db import connection
from pyproj import Geod
from shapely import get_parts, segmentize, unary_union
from shapely.affinity import translate
from shapely.geometry import MultiPoint, Polygon, box
from shapely.geometry.polygon import orient

from apps.project_management.models import Project, Site

CSV_COLUMNS = ["project_id", "project_name", "site_count", "area_ha"]
MAX_SEGMENT_DEGREES = 0.01  # ~1 km
SQ_METERS_PER_HECTARE = 10_000
WGS84 = Geod(ellps="WGS84")


class Command(BaseCommand):
    help = "Report the area (ha) of the convex hull around each project's sites, as CSV."

    def add_arguments(self, parser):
        parser.add_argument("--output", help="Write the CSV to this path instead of stdout")

    def handle(self, *args, **options):
        with _read_only_session():
            rows = project_areas()
        self._warn_about_invalid_sites(rows)

        output = options["output"]
        if output:
            # Not utf-8-sig: the BOM only helps Excel, and the CSV is mostly opened in Google Sheets.
            with open(output, "w", newline="", encoding="utf-8") as f:
                write_csv(rows, f)
            self.stdout.write(f"Wrote {len(rows)} projects to {output}")
        else:
            write_csv(rows, self.stdout)
            self.stdout.write("")

        # Sum the rounded values so the total matches what adding up the CSV column gives.
        project_area_sum = sum(round(row["area_ha"], 2) for row in rows)
        self.stdout.write(f"Sum of project areas (ha): {project_area_sum:.2f}")
        unique_area = unique_area_ha([row["hull"] for row in rows])
        self.stdout.write(f"Unique area covered (ha): {unique_area:.2f}")

    def _warn_about_invalid_sites(self, rows):
        # stderr, so the warning doesn't end up inside CSV written to stdout.
        for row in rows:
            if row["invalid_site_count"]:
                self.stderr.write(
                    f"Skipped {row['invalid_site_count']} site(s) with invalid coordinates in project "
                    f"{row['project_name']!r} ({row['project_id']})"
                )


@contextmanager
def _read_only_session():
    # Guards against accidental writes when this runs against staging/prod; same approach as read_only_shell.
    with connection.cursor() as cursor:
        cursor.execute("SET default_transaction_read_only = on")
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("RESET default_transaction_read_only")


def project_areas():
    """One row per live, unarchived project, largest area first."""
    projects = list(Project.objects.filter(archived=False).only("id", "name"))

    coords_by_project = defaultdict(list)
    invalid_counts = defaultdict(int)
    sites = Site.objects.filter(project__in=projects, archived=False).values_list(
        "project_id", "longitude", "latitude"
    )
    for project_id, lon, lat in sites:
        # The backend doesn't validate coordinate ranges, and out-of-range values break the hull math (NaN areas, hulls clipped out of the unique area).
        if is_valid_coordinate(lon, lat):
            coords_by_project[project_id].append((normalize_longitude(lon), lat))
        else:
            invalid_counts[project_id] += 1

    rows = []
    for project in projects:
        coords = coords_by_project[project.id]
        hull = convex_hull(coords)
        rows.append(
            {
                "project_id": project.id,
                "project_name": project.name,
                "site_count": len(coords),
                "invalid_site_count": invalid_counts[project.id],
                "area_ha": geodesic_area_ha(hull),
                "hull": hull,
            }
        )
    rows.sort(key=lambda row: (-row["area_ha"], row["project_name"]))
    return rows


def is_valid_coordinate(lon, lat):
    # Comparisons with NaN are False, so NaN latitudes fail the range check too.
    return math.isfinite(lon) and -90 <= lat <= 90


def normalize_longitude(lon):
    """The same longitude in [-180, 180), e.g. -190 -> 170."""
    return (lon + 180) % 360 - 180


def convex_hull(coords):
    """Convex hull around (lon, lat) points; an empty Polygon when they enclose no area."""
    if len(coords) < 3:
        return Polygon()
    hull = MultiPoint(unwrap_antimeridian(coords)).convex_hull
    # Duplicate or collinear points collapse to a Point or LineString, which encloses no area.
    return hull if hull.geom_type == "Polygon" else Polygon()


def geodesic_area_ha(geometry):
    """Area in hectares of the polygons in a geometry on the WGS84 ellipsoid, excluding holes."""
    # Shapes are drawn with straight edges on a flat lon/lat map but pyproj joins vertices by the shortest path on the globe, which bulges away from the drawn edge over long distances. A merged outline has different vertices than each project, so it bulges differently and can measure smaller than a project inside it; extra vertices make pyproj follow the drawn edges.
    geometry = segmentize(geometry, MAX_SEGMENT_DEGREES)
    polygons = [p for p in get_parts(geometry) if p.geom_type == "Polygon" and not p.is_empty]
    # pyproj's area sign follows ring direction; orient() makes outer rings positive and holes negative.
    area_m2 = sum(WGS84.geometry_area_perimeter(orient(polygon))[0] for polygon in polygons)
    return area_m2 / SQ_METERS_PER_HECTARE


def unique_area_ha(hulls):
    """Area in hectares covered by at least one hull, so overlaps count once."""
    return geodesic_area_ha(unary_union([_within_world_longitudes(hull) for hull in hulls]))


def _within_world_longitudes(hull):
    """Move any part of a hull east of 180° (see unwrap_antimeridian) back to -180°…, so hulls on either side of the line overlap where they should when merged."""
    in_range = hull.intersection(box(-180, -90, 180, 90))
    past_180 = hull.intersection(box(180, -90, 540, 90))
    return unary_union([in_range, translate(past_180, xoff=-360)])


def unwrap_antimeridian(coords):
    """Shift longitudes by 360° where needed so the points form one continuous range, cutting the map at the widest gap between them.

    Shapely treats lon/lat as flat x/y, so a cluster straddling ±180° (stored as 179.9 and -179.9) would otherwise be hulled as a band spanning the globe, and the hull would pick the wrong sites as its outline. pyproj measures unwrapped longitudes (e.g. 180.1) correctly.
    """
    lons = sorted({lon for lon, _lat in coords})
    widest_gap = lons[0] + 360 - lons[-1]  # the gap that wraps around through ±180°
    cut = None
    for west, east in pairwise(lons):
        if east - west > widest_gap:
            widest_gap, cut = east - west, west
    if cut is None:
        return coords
    return [(lon + 360 if lon <= cut else lon, lat) for lon, lat in coords]


def write_csv(rows, out):
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        writer.writerow(
            [row["project_id"], row["project_name"], row["site_count"], f"{row['area_ha']:.2f}"]
        )
