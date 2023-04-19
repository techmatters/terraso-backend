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
from django.db import transaction
from graphene import relay
from graphene_django import DjangoObjectType

from apps.project_management.models import Project, ProjectMembership

from .commons import BaseWriteMutation, TerrasoConnection


class ProjectNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = Project

        filter_fields = {"name": ["icontains"]}
        fields = ("name",)

        interfaces = (relay.Node,)
        connection_class = TerrasoConnection


class ProjectAddMutation(BaseWriteMutation):
    project = graphene.Field(ProjectNode, required=True)

    model_class = Project

    class Input:
        name = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        with transaction.atomic():
            result = super().mutate_and_get_payload(root, info, **kwargs)
            ProjectMembership.objects.create(
                member=info.context.user,
                project=result.project,
                membership=ProjectMembership.MANAGER,
            )
        return result
