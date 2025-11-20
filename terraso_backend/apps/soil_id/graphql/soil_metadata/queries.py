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
from graphene_django import DjangoObjectType

from apps.graphql.schema.commons import data_model_excluded_fields
from apps.graphql.schema.sites import SiteNode
from apps.soil_id.graphql.soil_metadata.types import UserMatchRatingEnum
from apps.soil_id.models.soil_metadata import SoilMetadata


class UserRatingEntry(graphene.ObjectType):
    """Represents a single user rating entry in the response"""

    soil_match_id = graphene.String(required=True)
    rating = graphene.Field(UserMatchRatingEnum, required=True)


class SoilMetadataNode(DjangoObjectType):
    site = graphene.Field(SiteNode, source="soil_metadata__site", required=True)

    # Backwards compatible: derive from user_ratings
    selected_soil_id = graphene.String()

    # New field: expose user_ratings as a list
    user_ratings = graphene.List(graphene.NonNull(UserRatingEntry), required=True)

    class Meta:
        model = SoilMetadata
        exclude = data_model_excluded_fields()

    def resolve_selected_soil_id(self, info):
        """
        Returns the soil_match_id marked as SELECTED in user_ratings.
        Maintains backwards compatibility for older clients.
        """
        return self.get_selected_soil_id()

    def resolve_user_ratings(self, info):
        """
        Returns user_ratings as a list of UserRatingEntry objects.
        """
        return [
            UserRatingEntry(soil_match_id=soil_match_id, rating=rating)
            for soil_match_id, rating in self.user_ratings.items()
        ]
