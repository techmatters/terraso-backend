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
from django.contrib.auth import get_user_model
from graphql import GraphQLError

from apps.project_management.models import Project, Site

from ..models import ExportToken
from .types import ExportToken as ExportTokenType
from .types import ResourceTypeEnum

User = get_user_model()


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
        return str(user.id) == resource_id

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
        user = info.context.user

        # Check permissions
        if not can_manage_export_token(user, resource_type, resource_id):
            raise GraphQLError(
                "You do not have permission to create an export token for this resource"
            )

        # Get the resource model based on type
        model_map = {
            "USER": User,
            "PROJECT": Project,
            "SITE": Site,
        }

        model = model_map[resource_type]
        try:
            resource = model.objects.get(pk=resource_id)
        except model.DoesNotExist:
            raise GraphQLError(f"{resource_type} not found")

        # Check if token already exists
        if resource.export_token:
            return CreateExportToken(
                token=ExportToken.objects.get(token=resource.export_token)
            )

        # Create new token
        token_obj = ExportToken.create_token(resource_type, resource_id)

        # Store token in resource
        resource.export_token = token_obj.token
        resource.save(update_fields=["export_token"])

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
