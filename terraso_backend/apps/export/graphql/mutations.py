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


class CreateExportToken(graphene.Mutation):
    class Arguments:
        resource_type = ResourceTypeEnum(required=True)
        resource_id = graphene.ID(required=True)

    tokens = graphene.Field(graphene.List(graphene.NonNull(ExportTokenType)))

    @staticmethod
    def mutate(root, info, resource_type, resource_id):
        user = info.context.user
        resource_type_str = resource_type.value

        # Verify resource exists and check permissions
        if resource_type_str == "USER":
            try:
                User.objects.get(pk=resource_id)
            except User.DoesNotExist:
                raise GraphQLError("User not found")

            if not user.has_perm("export.create_user_token", resource_id):
                raise GraphQLError(
                    "You do not have permission to create an export token for this resource"
                )

        elif resource_type_str == "PROJECT":
            try:
                project = Project.objects.get(pk=resource_id)
            except Project.DoesNotExist:
                raise GraphQLError("Project not found")

            if not user.has_perm("export.create_project_token", project):
                raise GraphQLError(
                    "You do not have permission to create an export token for this resource"
                )

        elif resource_type_str == "SITE":
            try:
                site = Site.objects.get(pk=resource_id)
            except Site.DoesNotExist:
                raise GraphQLError("Site not found")

            if not user.has_perm("export.create_site_token", site):
                raise GraphQLError(
                    "You do not have permission to create an export token for this resource"
                )

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
            if not user.has_perm("export.owns_token", token_obj):
                raise GraphQLError("You do not have permission to delete this export token")

            token_obj.delete()

            # Return all remaining tokens for the user
            return DeleteExportToken(tokens=list(get_user_tokens(user)))
        except ExportToken.DoesNotExist:
            raise GraphQLError("Export token not found")


class Mutation(graphene.ObjectType):
    create_export_token = CreateExportToken.Field()
    delete_export_token = DeleteExportToken.Field()
