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
from django.contrib.auth import get_user_model
from graphql import GraphQLError

from apps.project_management.models import Project, Site

from ..models import ExportToken
from .types import ExportToken as ExportTokenType
from .types import ResourceTypeEnum

User = get_user_model()
logger = logging.getLogger(__name__)


def get_user_tokens(user):
    """Get all export tokens for the current user."""
    return ExportToken.objects.filter(user_id=str(user.id))


def can_manage_export_token(user, resource_type, resource_id):
    """
    Check if user has permission to create/delete export tokens for a resource.

    Rules (Option A - Most Restrictive):
    - USER: Only the user themselves
    - PROJECT: Only project managers/owners
    - SITE: Only site owner (unaffiliated) or project managers/owners (project sites)
    """
    if user.is_anonymous:
        return False

    if resource_type == "USER":
        # Users can only manage tokens for themselves
        user_id_str = str(user.id)
        result = user_id_str == resource_id
        logger.info(
            f"Export token USER permission check: "
            f"user.id={user.id} (type={type(user.id).__name__}), "
            f"str(user.id)={user_id_str}, "
            f"resource_id={resource_id} (type={type(resource_id).__name__}), "
            f"comparison result={result}"
        )
        return result

    elif resource_type == "PROJECT":
        # Only project managers/owners can manage tokens
        try:
            project = Project.objects.get(pk=resource_id)
            membership = project.membership_list.memberships.filter(
                user=user,
                user_role__in=["MANAGER", "OWNER"],
                deleted_at__isnull=True,
            ).exists()
            return membership
        except Project.DoesNotExist:
            return False

    elif resource_type == "SITE":
        # Site owner OR project manager/owner can manage tokens
        try:
            site = Site.objects.get(pk=resource_id)

            # Check if user owns the site directly (unaffiliated site)
            if site.owner == user:
                return True

            # Check if user is manager/owner of site's project
            if site.project:
                membership = site.project.membership_list.memberships.filter(
                    user=user,
                    user_role__in=["MANAGER", "OWNER"],
                    deleted_at__isnull=True,
                ).exists()
                return membership

            return False
        except Site.DoesNotExist:
            return False

    return False


class CreateExportToken(graphene.Mutation):
    class Arguments:
        resource_type = ResourceTypeEnum(required=True)
        resource_id = graphene.ID(required=True)

    tokens = graphene.List(graphene.NonNull(ExportTokenType))

    @staticmethod
    def mutate(root, info, resource_type, resource_id):
        logger.info(
            f"CreateExportToken mutation called: "
            f"resource_type={resource_type} (type={type(resource_type).__name__}), "
            f"resource_id={resource_id}"
        )

        user = info.context.user
        logger.info(f"Authenticated user: {user.email} (id={user.id})")

        # Convert enum to string value
        resource_type_str = resource_type.value
        logger.info(f"Converted resource_type to string: '{resource_type_str}'")

        # Check permissions
        logger.info(f"Checking permissions for user {user.email} on {resource_type_str} {resource_id}")
        if not can_manage_export_token(user, resource_type_str, resource_id):
            logger.warning(f"Permission denied for user {user.email}")
            raise GraphQLError(
                "You do not have permission to create an export token for this resource"
            )
        logger.info(f"Permission check passed")

        # Verify resource exists
        model_map = {
            "USER": User,
            "PROJECT": Project,
            "SITE": Site,
        }

        model = model_map[resource_type_str]
        logger.info(f"Looking up {model.__name__} with pk={resource_id}")
        try:
            resource = model.objects.get(pk=resource_id)
            logger.info(f"Found resource: {resource}")
        except model.DoesNotExist:
            logger.error(f"{resource_type_str} with id {resource_id} not found")
            raise GraphQLError(f"{resource_type} not found")

        # Get or create token for this user-resource pair
        logger.info(f"Getting or creating token for user {user.id}, {resource_type_str} {resource_id}")
        try:
            token_obj, created = ExportToken.get_or_create_token(
                resource_type_str, resource_id, str(user.id)
            )
            if created:
                logger.info(f"Created new token: {token_obj.token}")
            else:
                logger.info(f"Returning existing token: {token_obj.token}")
        except Exception as e:
            logger.error(f"Failed to get or create token: {e}", exc_info=True)
            raise

        logger.info(f"CreateExportToken mutation completed successfully")

        # Return all tokens for the user
        user_tokens = get_user_tokens(user)
        return CreateExportToken(tokens=list(user_tokens))


class DeleteExportToken(graphene.Mutation):
    class Arguments:
        token = graphene.String(required=True)

    tokens = graphene.List(graphene.NonNull(ExportTokenType))

    @staticmethod
    def mutate(root, info, token):
        user = info.context.user

        try:
            token_obj = ExportToken.objects.get(token=token)

            # Check permissions - user must have rights to manage this resource's token
            if not can_manage_export_token(
                user, token_obj.resource_type, token_obj.resource_id
            ):
                raise GraphQLError(
                    "You do not have permission to delete this export token"
                )

            # Delete token (no need to clear resource.export_token field)
            token_obj.delete()

            # Return all remaining tokens for the user
            user_tokens = get_user_tokens(user)
            return DeleteExportToken(tokens=list(user_tokens))
        except ExportToken.DoesNotExist:
            raise GraphQLError("Export token not found")


class Mutation(graphene.ObjectType):
    create_export_token = CreateExportToken.Field()
    delete_export_token = DeleteExportToken.Field()
