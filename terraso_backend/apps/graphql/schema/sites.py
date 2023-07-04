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
from datetime import datetime

import django_filters
import graphene
from django.db.models import Q
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import GlobalIDFilter

from apps.audit_logs import api as audit_log_api
from apps.project_management.models import Project, Site, sites

from .commons import BaseWriteMutation, TerrasoConnection
from .constants import MutationTypes


class SiteFilter(django_filters.FilterSet):
    visible_to_user__id = GlobalIDFilter(method="filter_visible_to_user")

    class Meta:
        model = Site
        fields = ["name", "owner", "project", "project__id", "archived"]

    order_by = django_filters.OrderingFilter(
        fields=(
            ("updated_at", "updated_at"),
            ("created_at", "created_at"),
        )
    )

    def filter_visible_to_user(self, queryset, name, id):
        return queryset.filter(Q(project__group__memberships__user__id=id) | Q(owner__id=id))


class SiteNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = Site

        fields = ("name", "latitude", "longitude", "project", "archived")
        filterset_class = SiteFilter

        interfaces = (relay.Node,)
        connection_class = TerrasoConnection

    @classmethod
    def get_queryset(cls, queryset, info):
        user = info.context.user
        if user.is_anonymous:
            return queryset.none()
        return sites.filter_only_sites_user_owner_or_member(user, queryset)


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
        log = cls.get_logger()
        user = info.context.user
        if not cls.is_update(kwargs):
            kwargs["created_by"] = user

        client_time = kwargs.pop("client_time", None)
        if not client_time:
            client_time = datetime.now()

        adding_to_project = "project_id" in kwargs
        if adding_to_project:
            project = cls.get_or_throw(Project, "project_id", kwargs["project_id"])
            if not user.has_perm(Project.get_perm("add_site"), project):
                raise cls.not_allowed(MutationTypes.ADD)
            kwargs["project"] = project
        else:
            kwargs["owner"] = info.context.user

        result = super().mutate_and_get_payload(root, info, **kwargs)
        if result.errors:
            return result

        site = result.site
        metadata = {
            "latitude": kwargs["latitude"],
            "longitude": kwargs["longitude"],
            "name": kwargs["name"],
        }
        if kwargs.get("project_id", None):
            metadata["project_id"] = kwargs["project_id"]
        log.log(
            user=user,
            action=audit_log_api.CREATE,
            resource=site,
            metadata=metadata,
            client_time=client_time,
        )
        return result


class SiteUpdateMutation(BaseWriteMutation):
    site = graphene.Field(SiteNode)

    model_class = Site

    class Input:
        id = graphene.ID(required=True)
        name = graphene.String()
        latitude = graphene.Float()
        longitude = graphene.Float()

        project_id = graphene.ID()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        log = cls.get_logger()
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
        if not user.has_perm(Project.get_perm("add_site"), project):
            raise cls.not_allowed(MutationTypes.UPDATE)
        site.add_to_project(project)

        client_time = kwargs.get("client_time", None)
        if not client_time:
            client_time = datetime.now()

        metadata = {}
        for key, value in kwargs.items():
            if key == "id":
                continue
            metadata[key] = value
        if project_id:
            metadata["project_name"] = project.name

        log.log(
            user=user,
            action=audit_log_api.CHANGE,
            resource=site,
            metadata=metadata,
            client_time=client_time,
        )

        return result
