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
        project_id = graphene.ID()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        adding_to_project = "project_id" in kwargs
        if adding_to_project:
            project = cls.get_or_throw(Project, "project_id", kwargs["project_id"])
            kwargs["project"] = project
        else:
            kwargs["owner"] = info.context.user
        return super().mutate_and_get_payload(root, info, **kwargs)


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
        user = info.context.user
        site = cls.get_or_throw(Site, "id", kwargs["id"])
        if not user.has_perm(Site.get_perm("change"), site):
            raise cls.not_allowed(MutationTypes.UPDATE)
        project_id = kwargs.pop("project_id", False)
        result = super().mutate_and_get_payload(root, info, **kwargs)
        if not project_id:
            return result
        site = result.site
        project = Project.objects.get(id=project_id)
        if not user.has_perm(Project.get_perm("change"), project):
            raise cls.not_allowed(MutationTypes.UPDATE)
        site.add_to_project(project)
        return result
