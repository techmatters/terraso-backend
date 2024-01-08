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
from django.conf import settings
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import SharedResource

from . import GroupNode, LandscapeNode
from .commons import TerrasoConnection
from .data_entries import DataEntryNode
from .visualization_config import VisualizationConfigNode


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
