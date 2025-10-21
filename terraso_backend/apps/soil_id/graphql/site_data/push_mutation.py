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
import structlog
from django.db import transaction
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

        # Validate at least one is provided
        if not soil_data_entries and not soil_metadata_entries:
            raise ValidationError(
                "At least one of soilDataEntries or soilMetadataEntries must be provided"
            )

        user = info.context.user
        soil_data_results = None
        soil_data_error = None
        soil_metadata_results = None
        soil_metadata_error = None

        # Process soil_data entries with separate error handling
        if soil_data_entries:
            soil_data_results = []
            try:
                # Use separate transactions like SoilDataPush does
                with transaction.atomic():
                    history_entries = SoilDataPush.log_soil_data_push(user, soil_data_entries)

                with transaction.atomic():
                    for entry, history_entry in zip(soil_data_entries, history_entries):
                        soil_data_results.append(
                            SoilDataPush.mutate_and_get_entry_result(
                                user=user, soil_data_entry=entry, history_entry=history_entry
                            )
                        )
            except Exception as e:
                logger.exception("Unexpected error processing soil data entries")
                soil_data_error = str(e)

        # Process soil_metadata entries with separate error handling
        if soil_metadata_entries:
            soil_metadata_results = []
            try:
                with transaction.atomic():
                    for entry in soil_metadata_entries:
                        soil_metadata_results.append(
                            SoilMetadataPush.mutate_and_get_entry_result(
                                user=user, soil_metadata_entry=entry
                            )
                        )
            except Exception as e:
                logger.exception("Unexpected error processing soil metadata entries")
                soil_metadata_error = str(e)

        return cls(
            soil_data_results=soil_data_results,
            soil_data_error=soil_data_error,
            soil_metadata_results=soil_metadata_results,
            soil_metadata_error=soil_metadata_error,
        )
