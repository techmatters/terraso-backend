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
        return str(user.id) == resource_id

    elif resource_type == "PROJECT":
        # Only project managers/owners can manage tokens
        try:
            project = Project.objects.get(pk=resource_id)
            return project.membership_list.memberships.filter(
                user=user,
                user_role__in=["MANAGER", "OWNER"],
                deleted_at__isnull=True,
            ).exists()
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
                return site.project.membership_list.memberships.filter(
                    user=user,
                    user_role__in=["MANAGER", "OWNER"],
                    deleted_at__isnull=True,
                ).exists()

            return False
        except Site.DoesNotExist:
            return False

    return False


class CreateExportToken(graphene.Mutation):
    class Arguments:
        resource_type = ResourceTypeEnum(required=True)
        resource_id = graphene.ID(required=True)

    tokens = graphene.Field(graphene.List(graphene.NonNull(ExportTokenType)))

    @staticmethod
    def mutate(root, info, resource_type, resource_id):
        user = info.context.user
        resource_type_str = resource_type.value

        # Check permissions
        if not can_manage_export_token(user, resource_type_str, resource_id):
            raise GraphQLError(
                "You do not have permission to create an export token for this resource"
            )

        # Verify resource exists
        model_map = {
            "USER": User,
            "PROJECT": Project,
            "SITE": Site,
        }

        model = model_map[resource_type_str]
        try:
            model.objects.get(pk=resource_id)
        except model.DoesNotExist:
            raise GraphQLError(f"{resource_type} not found")

        # Get or create token for this user-resource pair
        ExportToken.get_or_create_token(resource_type_str, resource_id, str(user.id))

        # Return all tokens for the user
        return CreateExportToken(tokens=list(get_user_tokens(user)))


class DeleteExportToken(graphene.Mutation):
    class Arguments:
        token = graphene.String(required=True)

    tokens = graphene.Field(graphene.List(graphene.NonNull(ExportTokenType)))

    @staticmethod
    def mutate(root, info, token):
        user = info.context.user

        try:
            token_obj = ExportToken.objects.get(token=token)

            # Check permissions - user must have rights to manage this resource's token
            if not can_manage_export_token(user, token_obj.resource_type, token_obj.resource_id):
                raise GraphQLError("You do not have permission to delete this export token")

            token_obj.delete()

            # Return all remaining tokens for the user
            return DeleteExportToken(tokens=list(get_user_tokens(user)))
        except ExportToken.DoesNotExist:
            raise GraphQLError("Export token not found")


class Mutation(graphene.ObjectType):
    create_export_token = CreateExportToken.Field()
    delete_export_token = DeleteExportToken.Field()
