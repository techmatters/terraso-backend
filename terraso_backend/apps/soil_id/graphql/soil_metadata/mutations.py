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
from django.db import transaction
from django.forms import ValidationError

from apps.graphql.schema.commons import BaseWriteMutation
from apps.graphql.schema.constants import MutationTypes
from apps.project_management.models.sites import Site
from apps.project_management.permission_rules import Context
from apps.project_management.permission_table import SiteAction, check_site_permission
from apps.soil_id.graphql.soil_metadata.queries import SoilMetadataNode
from apps.soil_id.graphql.soil_metadata.types import SoilMetadataInputs
from apps.soil_id.models.soil_metadata import SoilMetadata


class SoilMetadataUpdateMutation(BaseWriteMutation):
    soil_metadata = graphene.Field(SoilMetadataNode)
    model_class = SoilMetadata

    class Input(SoilMetadataInputs):
        site_id = graphene.ID(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, site_id, **kwargs):
        site = cls.get_or_throw(Site, "id", site_id)

        user = info.context.user
        if not check_site_permission(user, SiteAction.ENTER_DATA, Context(site=site)):
            raise cls.not_allowed(MutationTypes.UPDATE)

        if not hasattr(site, "soil_metadata"):
            site.soil_metadata = SoilMetadata()

        with transaction.atomic():
            # Old client: update via selected_soil_id
            if "selected_soil_id" in kwargs:
                selected_soil_id = kwargs.pop("selected_soil_id")
                site.soil_metadata.set_selected_soil_id(selected_soil_id)

            # New client: update via user_ratings
            if "user_ratings" in kwargs:
                input_user_ratings = kwargs.pop("user_ratings")

                input_ratings_dict = {
                    rating["soil_match_id"]: rating["rating"].value for rating in input_user_ratings
                }

                input_selected_soils = [
                    soil_match_id
                    for soil_match_id, rating in input_ratings_dict.items()
                    if rating == SoilMetadata.UserMatchRating.SELECTED.value
                ]
                if len(input_selected_soils) > 1:
                    raise ValidationError(
                        f"There should only be a single selected soil, but found {len(input_selected_soils)}: "
                        f"{', '.join(input_selected_soils)}"
                    )
                # If there is a selected soil in the new ratings, remove any existing SELECTED ratings
                if input_selected_soils:
                    site.soil_metadata.user_ratings = {
                        soil_match_id: rating
                        for soil_match_id, rating in site.soil_metadata.user_ratings.items()
                        if rating != SoilMetadata.UserMatchRating.SELECTED.value
                    }

                site.soil_metadata.user_ratings = (
                    site.soil_metadata.user_ratings | input_ratings_dict
                )
            kwargs["model_instance"] = site.soil_metadata
            result = super().mutate_and_get_payload(root, info, **kwargs)
        return result
