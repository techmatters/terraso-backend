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


def can_create_export_token(user, resource_type, resource_id):
    """
    Check if user has permission to CREATE an export token for a resource.
    User must have access to the underlying resource.

    Rules:
    - USER: Only the user themselves
    - PROJECT: Any project member
    - SITE: Site owner (unaffiliated) or any project member (project sites)
    """
    if user.is_anonymous:
        return False

    if resource_type == "USER":
        # Users can only create tokens for themselves
        return str(user.id) == resource_id

    elif resource_type == "PROJECT":
        # Any project member can create their own token
        try:
            project = Project.objects.get(pk=resource_id)
            return project.membership_list.memberships.filter(
                user=user,
                deleted_at__isnull=True,
            ).exists()
        except Project.DoesNotExist:
            return False

    elif resource_type == "SITE":
        # Site owner OR any project member can create their own token
        try:
            site = Site.objects.get(pk=resource_id)

            # Check if user owns the site directly (unaffiliated site)
            if site.owner == user:
                return True

            # Check if user is a member of site's project
            if site.project:
                return site.project.membership_list.memberships.filter(
                    user=user,
                    deleted_at__isnull=True,
                ).exists()

            return False
        except Site.DoesNotExist:
            return False

    return False


def user_owns_token(user, token_obj):
    """Check if user owns this token (for view/delete operations)."""
    return str(user.id) == token_obj.user_id


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
        if not can_create_export_token(user, resource_type_str, resource_id):
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

            # Check permissions - user can only delete their own tokens
            if not user_owns_token(user, token_obj):
                raise GraphQLError("You do not have permission to delete this export token")

            token_obj.delete()

            # Return all remaining tokens for the user
            return DeleteExportToken(tokens=list(get_user_tokens(user)))
        except ExportToken.DoesNotExist:
            raise GraphQLError("Export token not found")


class Mutation(graphene.ObjectType):
    create_export_token = CreateExportToken.Field()
    delete_export_token = DeleteExportToken.Field()
