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
import rules
import structlog
from django.conf import settings
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import SharedResource
from apps.graphql.exceptions import GraphQLNotAllowedException, GraphQLNotFoundException

from . import GroupNode, LandscapeNode
from .commons import BaseWriteMutation, TerrasoConnection
from .constants import MutationTypes
from .data_entries import DataEntryNode
from .visualization_config import VisualizationConfigNode

logger = structlog.get_logger(__name__)


class SourceNode(graphene.Union):
    class Meta:
        types = (VisualizationConfigNode, DataEntryNode)


class TargetNode(graphene.Union):
    class Meta:
        types = (GroupNode, LandscapeNode)


class SharedResourceNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)
    source = graphene.Field(SourceNode)
    target = graphene.Field(TargetNode)
    share_url = graphene.String()

    class Meta:
        model = SharedResource
        fields = ["id", "share_access"]
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection

    def resolve_source(self, info, **kwargs):
        return self.source

    def resolve_target(self, info, **kwargs):
        return self.target

    def resolve_share_url(self, info, **kwargs):
        return f"{settings.API_ENDPOINT}/shared-data/download/{self.share_uuid}"


class SharedResourceUpdateMutation(BaseWriteMutation):
    shared_resource = graphene.Field(SharedResourceNode)

    model_class = SharedResource

    class Input:
        id = graphene.ID(required=True)
        share_access = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user

        try:
            shared_resource = SharedResource.objects.get(pk=kwargs["id"])
        except SharedResource.DoesNotExist:
            logger.error(
                "SharedResource not found",
                extra={"shared_resource_id": kwargs["id"]},
            )
            raise GraphQLNotFoundException(field="id", model_name=SharedResource.__name__)

        if not rules.test_rule("allowed_to_change_shared_resource", user, shared_resource):
            logger.info(
                "Attempt to update a SharedResource, but user lacks permission",
                extra={"user_id": user.pk, "shared_resource_id": str(shared_resource.pk)},
            )
            raise GraphQLNotAllowedException(
                model_name=SharedResource.__name__, operation=MutationTypes.UPDATE
            )
        kwargs["share_access"] = SharedResource.get_share_access_from_text(kwargs["share_access"])
        return super().mutate_and_get_payload(root, info, **kwargs)
