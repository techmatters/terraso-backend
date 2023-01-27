# Copyright © 2021-2023 Technology Matters
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
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import TaxonomyTerm

from .commons import TerrasoConnection

logger = structlog.get_logger(__name__)


class TaxonomyTermNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = TaxonomyTerm
        filter_fields = {
            "type": ["exact", "in"],
        }
        fields = (
            "value_original",
            "value_es",
            "value_en",
            "type",
            "slug",
        )
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection
