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

from apps.core.models.users import User
from apps.graphql.schema.commons import BaseWriteMutation
from apps.project_management.models.sites import Site
from apps.project_management.permission_rules import Context
from apps.project_management.permission_table import SiteAction, check_site_permission
from apps.soil_id.graphql.soil_metadata.queries import SoilMetadataNode
from apps.soil_id.graphql.soil_metadata.types import UserRatingInput
from apps.soil_id.models.soil_metadata import SoilMetadata

logger = structlog.get_logger(__name__)


class SoilMetadataPushEntrySuccess(graphene.ObjectType):
    soil_metadata = graphene.Field(SoilMetadataNode, required=True)


class SoilMetadataPushFailureReason(graphene.Enum):
    DOES_NOT_EXIST = "DOES_NOT_EXIST"
    NOT_ALLOWED = "NOT_ALLOWED"
    INVALID_DATA = "INVALID_DATA"


class SoilMetadataPushEntryFailure(graphene.ObjectType):
    reason = graphene.Field(SoilMetadataPushFailureReason, required=True)


class SoilMetadataPushEntryResult(graphene.Union):
    class Meta:
        types = (SoilMetadataPushEntrySuccess, SoilMetadataPushEntryFailure)


class SoilMetadataPushEntry(graphene.ObjectType):
    site_id = graphene.ID(required=True)
    result = graphene.Field(SoilMetadataPushEntryResult, required=True)


class SoilMetadataPushInputEntry(graphene.InputObjectType):
    site_id = graphene.ID(required=True)
    user_ratings = graphene.Field(graphene.List(graphene.NonNull(UserRatingInput)), required=True)


class SoilMetadataPush(BaseWriteMutation):
    """
    Note: as of 2025-10 this mutation is not exposed on its own; it is only used as part of SiteDataPush (similar to how SiteDataPush uses SoilDataPush).
    """

    results = graphene.Field(graphene.List(graphene.NonNull(SoilMetadataPushEntry)), required=True)

    class Input:
        soil_metadata_entries = graphene.Field(
            graphene.List(graphene.NonNull(SoilMetadataPushInputEntry)), required=True
        )

    @staticmethod
    def validate_site_for_metadata_update(user: User, site_id: str):
        site = Site.objects.filter(id=site_id).first()

        if site is None:
            return None, SoilMetadataPushFailureReason.DOES_NOT_EXIST

        if not check_site_permission(user, SiteAction.ENTER_DATA, Context(site=site)):
            return None, SoilMetadataPushFailureReason.NOT_ALLOWED

        if not hasattr(site, "soil_metadata"):
            site.soil_metadata = SoilMetadata(site=site)

        return site.soil_metadata, None

    @staticmethod
    def convert_and_validate_user_ratings(user_ratings_input: list[dict]) -> dict[str, str]:
        """
        Converts user ratings input to a dictionary and validates that at most
        one rating has SELECTED status
        """
        user_ratings_dict = {}
        selected_count = 0
        for rating_entry in user_ratings_input:
            soil_match_id = rating_entry["soil_match_id"]
            rating_str = rating_entry["rating"].value
            if rating_str == "SELECTED":
                selected_count += 1
            user_ratings_dict[soil_match_id] = rating_str
        if selected_count > 1:
            raise ValidationError("Only a single selected soil is allowed across all user ratings")

        return user_ratings_dict

    @staticmethod
    def mutate_and_get_entry_result(user: User, soil_metadata_entry: dict):
        site_id = soil_metadata_entry["site_id"]
        user_ratings_input = soil_metadata_entry["user_ratings"]

        try:
            soil_metadata, reason = SoilMetadataPush.validate_site_for_metadata_update(
                user=user, site_id=site_id
            )
            if soil_metadata is None:
                return SoilMetadataPushEntry(
                    site_id=site_id, result=SoilMetadataPushEntryFailure(reason=reason)
                )

            user_ratings_dict = SoilMetadataPush.convert_and_validate_user_ratings(
                user_ratings_input
            )

            # Completely replace user_ratings (not merge)
            soil_metadata.user_ratings = user_ratings_dict
            soil_metadata.save()

            return SoilMetadataPushEntry(
                site_id=site_id, result=SoilMetadataPushEntrySuccess(soil_metadata=soil_metadata)
            )

        except ValidationError:
            return SoilMetadataPushEntry(
                site_id=site_id,
                result=SoilMetadataPushEntryFailure(
                    reason=SoilMetadataPushFailureReason.INVALID_DATA
                ),
            )

    @classmethod
    def mutate_and_get_payload(cls, root, info, soil_metadata_entries: list[dict]):
        results = []
        user = info.context.user

        for entry in soil_metadata_entries:
            results.append(
                SoilMetadataPush.mutate_and_get_entry_result(user=user, soil_metadata_entry=entry)
            )

        return cls(results=results)
