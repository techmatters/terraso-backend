# Copyright © 2021-2025 Technology Matters
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
from graphql import GraphQLError

from ..models import ExportToken
from .mutations import can_manage_export_token
from .types import ExportToken as ExportTokenType
from .types import ResourceTypeEnum


class Query(graphene.ObjectType):
    export_token = graphene.Field(
        ExportTokenType,
        resource_type=ResourceTypeEnum(required=True),
        resource_id=graphene.ID(required=True),
    )

    @staticmethod
    def resolve_export_token(root, info, resource_type, resource_id):
        user = info.context.user

        # Check permissions - user must have rights to view this resource's token
        if not can_manage_export_token(user, resource_type, resource_id):
            raise GraphQLError(
                "You do not have permission to view the export token for this resource"
            )

        try:
            return ExportToken.objects.get(
                resource_type=resource_type, resource_id=resource_id
            )
        except ExportToken.DoesNotExist:
            return None
