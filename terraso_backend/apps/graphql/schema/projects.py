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
from graphene import relay
from graphene_django import DjangoObjectType

from apps.audit_logs import api as log_api
from apps.audit_logs import services as log_services
from apps.project_management.models import Project

from .commons import BaseWriteMutation, TerrasoConnection


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
        logger = log_services.new_audit_logger()
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
            metadata=metadata
        )
        return result
