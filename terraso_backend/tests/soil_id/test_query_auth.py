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

from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser

from apps.graphql.exceptions import GraphQLNotAllowedException
from apps.soil_id.graphql.soil_id.queries import SoilId, resolve_soil_id

pytestmark = pytest.mark.django_db


def _info_for(user):
    return SimpleNamespace(context=SimpleNamespace(user=user))


def test_resolve_soil_id_rejects_anonymous():
    """Soil ID lookups must reject anonymous callers (regression: the
    resolvers previously ignored the user, allowing anonymous access)."""
    with pytest.raises(GraphQLNotAllowedException):
        resolve_soil_id(None, _info_for(AnonymousUser()))


def test_resolve_soil_id_allows_authenticated(user):
    """Any authenticated user (including partner service accounts) passes the
    gate; the lookup itself is exercised by the integration tests."""
    assert isinstance(resolve_soil_id(None, _info_for(user)), SoilId)
