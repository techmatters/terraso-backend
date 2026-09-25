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

import re

from apps.soil_id.graphql.soil_id.resolvers import resolve_soil_id_algorithm_version


def test_resolve_returns_installed_soil_id_version():
    # The resolver surfaces the installed soil-id's version verbatim; the semver
    # format itself is asserted in the soil-id repo (test_version.py). This just
    # verifies the plumbing, so it passes regardless of the currently-pinned build.
    from soil_id.__version__ import __version__ as installed

    assert resolve_soil_id_algorithm_version(None, None) == installed


def test_resolve_version_is_dotted():
    # Every supported build ships a version, so the resolver always returns a
    # dotted semver — never None (the field is non-null in the schema).
    v = resolve_soil_id_algorithm_version(None, None)
    assert v is not None and re.fullmatch(r"\d+(\.\d+)+", v), v
