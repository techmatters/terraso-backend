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
import django_filters
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


class SiteFilter(django_filters.FilterSet):
    class Meta:
        model = Site
        fields = ["name", "created_by", "project"]

    order_by = django_filters.OrderingFilter(
        fields=(
            ("updated_at", "updated_at"),
            ("created_at", "created_at"),
        )
    )


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
        user = info.context.user

        if not cls.is_update(kwargs):
            kwargs["created_by"] = user

        if "project_id" in kwargs:
            project = Project.objects.get(id=kwargs.pop("project_id"))
            if not user.has_perm(Project.get_perm("change"), project):
                cls.not_allowed(MutationTypes.UPDATE)
            kwargs["project"] = project

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
        if "project_id" in kwargs:
            user = info.context.user
            site = Site.objects.get(id=kwargs["id"])
            project = Project.objects.get(id=kwargs.pop("project_id"))
            if not user.has_perm(Site.get_perm("change"), site) or not user.has_perm(
                Project.get_perm("change"), project
            ):
                cls.not_allowed(MutationTypes.UPDATE)
            kwargs["project"] = project
        return super().mutate_and_get_payload(root, info, **kwargs)
