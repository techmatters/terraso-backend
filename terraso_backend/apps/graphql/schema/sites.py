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
from graphene import relay
from graphene_django import DjangoObjectType

from apps.project_management.models import Project, Site

from .commons import BaseWriteMutation, TerrasoConnection
from .constants import MutationTypes


class SiteNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = Site

        filter_fields = {"name": ["icontains"]}
        fields = ("name", "latitude", "longitude", "project")

        interfaces = (relay.Node,)
        connection_class = TerrasoConnection


class SiteAddMutation(BaseWriteMutation):
    site = graphene.Field(SiteNode, required=True)

    model_class = Site

    class Input:
        name = graphene.String(required=True)
        latitude = graphene.Float(required=True)
        longitude = graphene.Float(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        kwargs["creator"] = info.context.user
        result = super().mutate_and_get_payload(root, info, **kwargs)
        return result


class SiteEditMutation(BaseWriteMutation):
    site = graphene.Field(SiteNode, required=True)

    model_class = Site

    class Input:
        id = graphene.ID(required=True)
        name = graphene.String()
        latitude = graphene.Float()
        longitude = graphene.Float()

        project_id = graphene.ID()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        if "project_id" in kwargs:
            project = Project.objects.get(id=kwargs.pop("project_id"))
            # TODO: Eventually we should check project permissions
            # Members should be able to add sites as well
            if not project.is_manager(info.context.user):
                raise cls.not_allowed(MutationTypes.UPDATE)
            kwargs["project"] = project
        result = super().mutate_and_get_payload(root, info, **kwargs)

        return result
