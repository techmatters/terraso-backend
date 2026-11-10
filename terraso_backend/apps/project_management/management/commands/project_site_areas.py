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

A project's area is the convex hull around its sites (deleted and archived ones excluded), measured on the WGS84 ellipsoid. Projects with fewer than 3 distinct, non-collinear sites get 0. The output ends with the sum of all project areas, so overlapping projects are counted more than once.

Usage:
    python manage.py project_site_areas                     # CSV to stdout
    python manage.py project_site_areas --output areas.csv  # CSV to a file
"""

import csv
from collections import defaultdict
from contextlib import contextmanager
from itertools import pairwise

from django.core.management.base import BaseCommand
from django.db import connection
from pyproj import Geod
from shapely.geometry import MultiPoint

from apps.project_management.models import Project, Site

CSV_COLUMNS = ["project_id", "project_name", "site_count", "area_ha"]
SQ_METERS_PER_HECTARE = 10_000
WGS84 = Geod(ellps="WGS84")


class Command(BaseCommand):
    help = "Report the area (ha) of the convex hull around each project's sites, as CSV."

    def add_arguments(self, parser):
        parser.add_argument("--output", help="Write the CSV to this path instead of stdout")

    def handle(self, *args, **options):
        with _read_only_session():
            rows = project_areas()

        output = options["output"]
        if output:
            with open(output, "w", newline="") as f:
                write_csv(rows, f)
            self.stdout.write(f"Wrote {len(rows)} projects to {output}")
        else:
            write_csv(rows, self.stdout)
            self.stdout.write("")

        total = sum(row["area_ha"] for row in rows)
        self.stdout.write(f"Total area (ha): {total:.2f}")


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
    sites = Site.objects.filter(project__in=projects, archived=False).values_list(
        "project_id", "longitude", "latitude"
    )
    for project_id, lon, lat in sites:
        coords_by_project[project_id].append((lon, lat))

    rows = [
        {
            "project_id": project.id,
            "project_name": project.name,
            "site_count": len(coords_by_project[project.id]),
            "area_ha": hull_area_ha(coords_by_project[project.id]),
        }
        for project in projects
    ]
    rows.sort(key=lambda row: (-row["area_ha"], row["project_name"]))
    return rows


def hull_area_ha(coords):
    """Geodesic area in hectares of the convex hull around (lon, lat) points."""
    if len(coords) < 3:
        return 0.0
    hull = MultiPoint(unwrap_antimeridian(coords)).convex_hull
    # Duplicate or collinear points collapse to a Point or LineString, which encloses no area.
    if hull.geom_type != "Polygon":
        return 0.0
    lons, lats = hull.exterior.xy
    area_m2, _perimeter = WGS84.polygon_area_perimeter(lons, lats)
    return abs(area_m2) / SQ_METERS_PER_HECTARE


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
