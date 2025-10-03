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

from django.db import models

from apps.core.models.commons import BaseModel
from apps.project_management.models.sites import Site


class SoilMetadata(BaseModel):
    site = models.OneToOneField(Site, on_delete=models.CASCADE, related_name="soil_metadata")

    class UserMatchRating(models.TextChoices):
        SELECTED = "SELECTED"
        REJECTED = "REJECTED"
        UNSURE = "UNSURE"

    # Maps soil_match_id (string) to rating (UserMatchRating value)
    # Example: {"soil_match_123": "SELECTED", "soil_match_456": "REJECTED"}
    user_ratings = models.JSONField(default=dict, blank=True)

    @property
    def selected_soil_id(self):
        """
        Property that returns the soil_match_id marked as SELECTED in user_ratings.
        Returns None if no soil match is selected.
        Used for backwards compatibility with older clients.
        """
        for soil_match_id, rating in self.user_ratings.items():
            if rating == SoilMetadata.UserMatchRating.SELECTED:
                return soil_match_id
        return None

    def get_selected_soil_id(self):
        """
        Returns the soil_match_id that is marked as SELECTED in user_ratings.
        Returns None if no soil match is selected.
        Used for backwards compatibility with older clients.
        """
        return self.selected_soil_id

    def set_selected_soil_id(self, soil_match_id):
        """
        Sets the given soil_match_id as SELECTED in user_ratings.
        Removes any other SELECTED ratings (only one can be selected at a time).
        Used for backwards compatibility when old clients update selected_soil_id.
        """
        if soil_match_id is None or soil_match_id == "":
            # Remove all SELECTED ratings
            self.user_ratings = {
                k: v
                for k, v in self.user_ratings.items()
                if v != SoilMetadata.UserMatchRating.SELECTED
            }
        else:
            # Remove any existing SELECTED ratings and add the new one
            self.user_ratings = {
                k: v
                for k, v in self.user_ratings.items()
                if v != SoilMetadata.UserMatchRating.SELECTED
            }
            self.user_ratings[soil_match_id] = SoilMetadata.UserMatchRating.SELECTED

    class Meta(BaseModel.Meta):
        verbose_name_plural = "soil metadata"
