# Copyright © 2021-2025 Technology Matters
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

from .transformers import flatten_site


def sites_to_csv(sites):
    """Convert a list of sites to CSV format"""
    flattened_sites = []
    for site in sites:
        flattened_sites.extend(flatten_site(site))

    fieldnames = list(flattened_sites[0].keys()) if flattened_sites else []
    csv_buffer = StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(flattened_sites)
    csv_buffer.seek(0)
    return csv_buffer.getvalue()