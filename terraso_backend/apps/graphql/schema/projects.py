# Copyright © 2023 Technology Matters
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

import graphene
from django.db import transaction
from django_filters import FilterSet
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import TypedFilter

from apps.audit_logs import api as log_api
from apps.project_management.models import Project
from apps.project_management.models.sites import Site

from .commons import BaseDeleteMutation, BaseWriteMutation, TerrasoConnection


class ProjectFilterSet(FilterSet):
    member = TypedFilter(field_name="group__memberships__user")

    class Meta:
        model = Project
        fields = {"name": ["exact", "icontains"]}


class ProjectNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = Project

        filterset_class = ProjectFilterSet
        fields = ("name", "privacy")

        interfaces = (relay.Node,)
        connection_class = TerrasoConnection


class ProjectPrivacy(graphene.Enum):
    PRIVATE = Project.PRIVATE
    PUBLIC = Project.PUBLIC


class ProjectAddMutation(BaseWriteMutation):
    skip_field_validation = ["group", "settings"]
    project = graphene.Field(ProjectNode, required=True)

    model_class = Project

    class Input:
        name = graphene.String(required=True)
        privacy = graphene.Field(ProjectPrivacy, required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        logger = cls.get_logger()
        user = info.context.user
        with transaction.atomic():
            group = Project.create_default_group(name=kwargs["name"])
            kwargs["group"] = group
            kwargs["privacy"] = kwargs["privacy"].value
            result = super().mutate_and_get_payload(root, info, **kwargs)
            result.project.add_manager(user)

        client_time = kwargs.get("client_time", None)
        if not client_time:
            client_time = datetime.now()
        action = log_api.CREATE
        metadata = {"name": kwargs["name"], "privacy": kwargs["privacy"]}
        logger.log(
            user=user,
            action=action,
            resource=result.project,
            client_time=client_time,
            metadata=metadata,
        )
        return result


class ProjectDeleteMutation(BaseDeleteMutation):
    project = graphene.Field(ProjectNode, required=True)

    model_class = Project

    class Input:
        id = graphene.ID(required=True)
        transfer_project_id = graphene.ID()

    @classmethod
    @transaction.atomic
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        project_id = kwargs["id"]
        project = cls.get_or_throw(Project, "id", project_id)
        if not user.has_perm(Project.get_perm("delete"), project):
            cls.not_allowed()
        if "transfer_project_id" in kwargs:
            transfer_project_id = kwargs["transfer_project_id"]
            transfer_project = cls.get_or_throw(Project, "id", transfer_project_id)
            if not user.has_perm(Project.get_perm("add"), transfer_project):
                cls.not_allowed()
            project_sites = project.site_set.all()
            for site in project_sites:
                site.project = transfer_project
            Site.objects.bulk_update(project_sites, ["project"])
        result = super().mutate_and_get_payload(root, info, **kwargs)
        return result


class ProjectArchiveMutation(BaseWriteMutation):
    project = graphene.Field(ProjectNode, required=True)

    model_class = Project

    class Input:
        id = graphene.ID(required=True)
        archived = graphene.Boolean(required=True)

    @classmethod
    @transaction.atomic
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        project_id = kwargs["id"]
        project = cls.get_or_throw(Project, "id", project_id)
        if not user.has_perm(Project.get_perm("archive"), project):
            cls.not_allowed()
        project_sites = project.site_set.all()
        for site in project_sites:
            site.archived = kwargs["archived"]
        Site.objects.bulk_update(project_sites, ["archived"])
        result = super().mutate_and_get_payload(root, info, **kwargs)
        return result


class ProjectUpdateMutation(BaseWriteMutation):
    project = graphene.Field(ProjectNode)

    model_class = Project

    class Input:
        id = graphene.ID(required=True)
        name = graphene.String()
        privacy = graphene.Field(ProjectPrivacy)

    @classmethod
    @transaction.atomic
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        project_id = kwargs["id"]
        project = cls.get_or_throw(Project, "id", project_id)
        if not user.has_perm(Project.get_perm("change"), project):
            cls.not_allowed()
        kwargs["privacy"] = kwargs["privacy"].value
        return super().mutate_and_get_payload(root, info, **kwargs)
