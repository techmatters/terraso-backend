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

import graphene
from django.db import transaction
from graphene import relay
from graphene_django import DjangoObjectType

from apps.project_management.models import Project
from apps.project_management.models.sites import Site

from .commons import BaseDeleteMutation, BaseWriteMutation, TerrasoConnection

class ProjectNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = Project

        filter_fields = {"name": ["icontains"]}
        fields = ("name",)

        interfaces = (relay.Node,)
        connection_class = TerrasoConnection


class ProjectPrivacy(graphene.Enum):
    PRIVATE = Project.PRIVATE
    PUBLIC = Project.PUBLIC


class ProjectAddMutation(BaseWriteMutation):
    project = graphene.Field(ProjectNode, required=True)

    model_class = Project

    class Input:
        name = graphene.String(required=True)
        privacy = graphene.Field(ProjectPrivacy, required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        with transaction.atomic():
            group = Project.create_default_group(name=kwargs["name"])
            kwargs["group"] = group
            kwargs["privacy"] = kwargs["privacy"].value
            result = super().mutate_and_get_payload(root, info, **kwargs)
            result.project.add_manager(info.context.user)
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
        project_id = kwargs['id']
        project = cls.get_or_throw('id', project_id)
        if not user.has_perm(Project.get_perm("delete"), project):
            cls.not_allowed()
        if 'transfer_project_id' in kwargs:
            transfer_project_id = kwargs['transfer_project_id']
            transfer_project = cls.get_or_throw('id', transfer_project_id)
            if not user.has_perm(Project.get_perm("add"), transfer_project):
                cls.not_allowed()
            project_sites = project.site_set.all()
            for site in project_sites:
                site.project = transfer_project
            Site.objects.bulk_update(project_sites, ["project"])
        result = super().mutate_and_get_payload(root, info, **kwargs)
        return result
