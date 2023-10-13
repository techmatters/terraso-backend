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
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import SharedResource

from . import DataEntryNode, GroupNode, LandscapeNode, VisualizationConfigNode
from .commons import TerrasoConnection


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

    class Meta:
        model = SharedResource
        fields = ["id"]
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection

    def resolve_source(self, info, **kwargs):
        return self.source

    def resolve_target(self, info, **kwargs):
        return self.target


class SharedResourcesMixin:
    shared_resources = graphene.List(SharedResourceNode)

    def resolve_shared_resources(self, info, **kwargs):
        return self.shared_resources.all()
