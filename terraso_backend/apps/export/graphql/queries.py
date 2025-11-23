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

import logging

import graphene
from graphql import GraphQLError

from ..models import ExportToken
from .mutations import can_manage_export_token
from .types import ExportToken as ExportTokenType
from .types import ResourceTypeEnum

logger = logging.getLogger(__name__)


class Query(graphene.ObjectType):
    export_token = graphene.Field(
        ExportTokenType,
        resource_type=ResourceTypeEnum(required=True),
        resource_id=graphene.ID(required=True),
    )

    @staticmethod
    def resolve_export_token(root, info, resource_type, resource_id):
        logger.info(
            f"exportToken query called: "
            f"resource_type={resource_type} (type={type(resource_type).__name__}), "
            f"resource_id={resource_id}"
        )

        user = info.context.user
        logger.info(f"Authenticated user: {user.email} (id={user.id})")

        # Convert enum to string value
        resource_type_str = resource_type.value
        logger.info(f"Converted resource_type to string: '{resource_type_str}'")

        # Check permissions - user must have rights to view this resource's token
        logger.info(f"Checking permissions for user {user.email} on {resource_type_str} {resource_id}")
        if not can_manage_export_token(user, resource_type_str, resource_id):
            logger.warning(f"Permission denied for user {user.email}")
            raise GraphQLError(
                "You do not have permission to view the export token for this resource"
            )
        logger.info(f"Permission check passed")

        try:
            token_obj = ExportToken.objects.get(
                resource_type=resource_type_str, resource_id=resource_id
            )
            logger.info(
                f"Found token - token={token_obj.token}, "
                f"resource_type={token_obj.resource_type}, "
                f"resource_id={token_obj.resource_id}"
            )
            return token_obj
        except ExportToken.DoesNotExist:
            logger.info(f"No export token found for {resource_type_str} {resource_id}")
            return None
