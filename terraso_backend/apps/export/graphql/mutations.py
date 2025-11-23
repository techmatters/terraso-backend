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

    token = graphene.Field(ExportTokenType)

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

        # Get the resource model based on type
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

        # Check if token already exists
        logger.info(f"Checking if export_token already exists: {resource.export_token}")
        if resource.export_token:
            logger.info(f"Token already exists, returning existing token: {resource.export_token}")
            token_obj = ExportToken.objects.get(token=resource.export_token)
            logger.info(
                f"Returning token object - token={token_obj.token}, "
                f"resource_type={token_obj.resource_type}, "
                f"resource_id={token_obj.resource_id}"
            )
            return CreateExportToken(token=token_obj)

        # Create new token
        logger.info(f"Creating new export token for {resource_type_str} {resource_id}")
        try:
            token_obj = ExportToken.create_token(resource_type_str, resource_id)
            logger.info(f"Created token object: {token_obj.token}")
        except Exception as e:
            logger.error(f"Failed to create token: {e}", exc_info=True)
            raise

        # Store token in resource
        logger.info(f"Storing token {token_obj.token} on resource")
        try:
            resource.export_token = token_obj.token
            resource.save(update_fields=["export_token"])
            logger.info(f"Successfully saved token to resource")
        except Exception as e:
            logger.error(f"Failed to save token to resource: {e}", exc_info=True)
            raise

        logger.info(f"CreateExportToken mutation completed successfully")
        return CreateExportToken(token=token_obj)


class DeleteExportToken(graphene.Mutation):
    class Arguments:
        token = graphene.String(required=True)

    success = graphene.Boolean()

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

            # Clear token from resource
            model_map = {
                "USER": User,
                "PROJECT": Project,
                "SITE": Site,
            }

            model = model_map[token_obj.resource_type]
            try:
                resource = model.objects.get(pk=token_obj.resource_id)
                resource.export_token = None
                resource.save(update_fields=["export_token"])
            except model.DoesNotExist:
                # Resource was deleted, but token still exists - just delete token
                pass

            # Delete token
            token_obj.delete()

            return DeleteExportToken(success=True)
        except ExportToken.DoesNotExist:
            raise GraphQLError("Export token not found")


class Mutation(graphene.ObjectType):
    create_export_token = CreateExportToken.Field()
    delete_export_token = DeleteExportToken.Field()
