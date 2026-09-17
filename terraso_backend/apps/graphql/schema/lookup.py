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

"""Root `lookup` namespace: queries that consult a third-party data source.

`Lookup.elevation` etc. are thin wrappers over external providers (Mapbox,
etc.) — no business logic on our side, no user data returned. Grouped here
(rather than under a business-domain namespace like `soilId`) because the
provider is what defines the surface, not our domain model. Auth-gated so
unauthenticated callers can't burn provider quota.
"""

import graphene

from apps.graphql.exceptions import GraphQLNotAllowedException
from apps.soil_id.graphql.soil_id.resolvers import resolve_elevation


class Lookup(graphene.ObjectType):
    """Third-party-backed data lookups (elevation, ...)."""

    elevation = graphene.Field(
        graphene.Float,
        latitude=graphene.Float(required=True),
        longitude=graphene.Float(required=True),
        resolver=resolve_elevation,
        description=(
            "Point elevation in meters (Mapbox Terrain-RGB), or null if unavailable. "
            "Same source as the soil-ID ranking's server-side elevation fallback."
        ),
    )


def resolve_lookup(parent, info):
    # Third-party lookups burn provider quota (Mapbox, etc.); require an
    # authenticated caller so anonymous clients can't hammer them.
    if info.context.user.is_anonymous:
        raise GraphQLNotAllowedException(
            model_name="Lookup", field="lookup", operation="read"
        )
    return Lookup()


lookup = graphene.Field(
    Lookup,
    required=True,
    resolver=resolve_lookup,
    description="Third-party-backed data lookups.",
)
