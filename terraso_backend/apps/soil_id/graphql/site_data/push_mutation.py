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

import graphene
import structlog
from django.forms import ValidationError

from apps.graphql.schema.commons import BaseWriteMutation
from apps.soil_id.graphql.soil_data.push_mutation import (
    SoilDataPush,
    SoilDataPushEntry,
    SoilDataPushInputEntry,
)
from apps.soil_id.graphql.soil_metadata.push_mutation import (
    SoilMetadataPush,
    SoilMetadataPushEntry,
    SoilMetadataPushInputEntry,
)

logger = structlog.get_logger(__name__)


class SiteDataPush(BaseWriteMutation):
    """
    To enable offline functionality.
    Pushes at least one of the following sub-mutations:
    - soil data
    - soil metadata (fully replaces user ratings)

    Partial updates are possible, if failure happens at the level of a sub-mutation, or more granularly within the sub-mutation.
    """

    soil_data_results = graphene.Field(
        graphene.List(graphene.NonNull(SoilDataPushEntry)), required=False
    )
    soil_data_error = graphene.String()
    soil_metadata_results = graphene.Field(
        graphene.List(graphene.NonNull(SoilMetadataPushEntry)), required=False
    )
    soil_metadata_error = graphene.String()

    class Input:
        soil_data_entries = graphene.Field(graphene.List(graphene.NonNull(SoilDataPushInputEntry)))
        soil_metadata_entries = graphene.Field(
            graphene.List(graphene.NonNull(SoilMetadataPushInputEntry))
        )

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        soil_data_entries = kwargs.get("soil_data_entries", [])
        soil_metadata_entries = kwargs.get("soil_metadata_entries", [])

        if not soil_data_entries and not soil_metadata_entries:
            raise ValidationError(
                "At least one of soilDataEntries or soilMetadataEntries must be provided"
            )

        soil_data_results = None
        soil_data_error = None
        soil_metadata_results = None
        soil_metadata_error = None

        if soil_data_entries:
            try:
                result = SoilDataPush.mutate_and_get_payload(
                    root, info, soil_data_entries=soil_data_entries
                )
                soil_data_results = result.results
            except Exception as e:
                logger.exception("Unexpected error pushing soil data entries")
                soil_data_error = str(e)

        if soil_metadata_entries:
            try:
                result = SoilMetadataPush.mutate_and_get_payload(
                    root, info, soil_metadata_entries=soil_metadata_entries
                )
                soil_metadata_results = result.results
            except Exception as e:
                logger.exception("Unexpected error pushing soil metadata entries")
                soil_metadata_error = str(e)

        return cls(
            soil_data_results=soil_data_results,
            soil_data_error=soil_data_error,
            soil_metadata_results=soil_metadata_results,
            soil_metadata_error=soil_metadata_error,
        )
