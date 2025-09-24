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

    # This value is used to support behavior with FF_select_soil flag off
    # And may also be used for manually entering selected soil in the future?
    selected_soil_id = models.CharField(blank=True, null=True)

    class Meta(BaseModel.Meta):
        verbose_name_plural = "soil metadata"


class UserMatchRating(BaseModel):
    soil_metadata = models.ForeignKey(
        SoilMetadata, on_delete=models.CASCADE, related_name="user_match_ratings"
    )

    class UserRating(models.TextChoices):
        SELECTED = "SELECTED"
        REJECTED = "REJECTED"
        UNSURE = "UNSURE"

    # TODO-cknipe: Why above is it ok to define a CharField without a max length? Should this be a CharField?
    match_id = models.TextField()
    # TODO-cknipe: UserRating.UNSURE.value? Or just UserRating.UNSURE?
    user_rating = models.CharField(choices=UserRating.choices, default=UserRating.UNSURE.value)
