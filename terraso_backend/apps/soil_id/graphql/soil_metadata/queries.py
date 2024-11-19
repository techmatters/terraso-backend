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
from apps.soil_id.models.soil_metadata import SoilMetadata


class SoilMetadataNode(DjangoObjectType):
    site = graphene.Field(SiteNode, source="soil_metadata__site", required=True)

    class Meta:
        model = SoilMetadata
        exclude = data_model_excluded_fields()
