# Copyright © 2024 Technology Matters
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


import graphene
from graphene.types.generic import GenericScalar

from apps.graphql.exceptions import GraphQLNotAllowedException
from apps.soil_id.graphql.soil_id.resolvers import (
    resolve_data_based_result,
    resolve_soil_id_algorithm_version,
    resolve_soil_id_explanation,
    resolve_soil_id_result,
)
from apps.soil_id.graphql.soil_id.types import DataBasedResult, SoilIdInputData, SoilIdResult


class SoilId(graphene.ObjectType):
    """Soil ID algorithm queries."""

    data_based_soil_matches = graphene.Field(
        graphene.NonNull(DataBasedResult),
        latitude=graphene.Float(required=True),
        longitude=graphene.Float(required=True),
        data=graphene.Argument(SoilIdInputData),
        resolver=resolve_data_based_result,
        description="DEPRECATED",
    )

    soil_matches = graphene.Field(
        graphene.NonNull(SoilIdResult),
        latitude=graphene.Float(required=True),
        longitude=graphene.Float(required=True),
        data=graphene.Argument(SoilIdInputData),
        resolver=resolve_soil_id_result,
    )

    soil_id_explanation = graphene.Field(
        GenericScalar,
        latitude=graphene.Float(required=True),
        longitude=graphene.Float(required=True),
        data=graphene.Argument(SoilIdInputData),
        resolver=resolve_soil_id_explanation,
        description=(
            "Full scoring trace (JSON) for the ranking at this location: how each "
            "candidate's location / horizon / site / color score was computed. Feeds "
            "the offline explain report (scripts/render_soil_explain.py in "
            "soil-id-algorithm). Null when unavailable (algorithm failure, no data, "
            "or a soil-id build without explain support)."
        ),
    )

    soil_id_algorithm_version = graphene.Field(
        graphene.NonNull(graphene.String),
        resolver=resolve_soil_id_algorithm_version,
        description=(
            "Semver (MAJOR.MINOR.PATCH) of the installed soil-ID algorithm. "
            "Clients cache soil-ID match results and flush them when MAJOR or MINOR "
            "changes (a result-affecting release); a PATCH bump does not change "
            "rankings and does not trigger a flush. Clients poll this on sync."
        ),
    )


def resolve_soil_id(parent, info):
    # Soil ID lookups require an authenticated caller. Anonymous access was
    # previously allowed because the resolvers ignored the user entirely;
    # gate it here at the single entry point so both soilMatches and the
    # deprecated dataBasedSoilMatches (and any future SoilId field) are
    # covered. Partner access is granted by issuing a service-account token.
    if info.context.user.is_anonymous:
        raise GraphQLNotAllowedException(model_name="SoilId", field="soilId", operation="read")
    return SoilId()


soil_id = graphene.Field(
    SoilId, required=True, resolver=resolve_soil_id, description="Soil ID algorithm Queries"
)
