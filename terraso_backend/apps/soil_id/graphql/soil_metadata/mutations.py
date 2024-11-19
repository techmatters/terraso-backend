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

        kwargs["model_instance"] = site.soil_metadata

        with transaction.atomic():
            result = super().mutate_and_get_payload(root, info, **kwargs)
        return result
