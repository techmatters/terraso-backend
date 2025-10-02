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
from graphene import Enum

from apps.soil_id.models.soil_metadata import UserMatchRating

# GraphQL Enum for UserMatchRating
UserMatchRatingEnum = Enum.from_enum(UserMatchRating)


class UserRatingInput(graphene.InputObjectType):
    """Input type for a single user rating entry"""

    soil_match_id = graphene.String(required=True)
    rating = graphene.Field(UserMatchRatingEnum, required=True)


class SoilMetadataInputs:
    # Deprecated: kept for backwards compatibility with older clients
    selected_soil_id = graphene.String()

    # New field: list of user ratings for soil matches
    user_ratings = graphene.List(UserRatingInput)
