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
from django_filters import FilterSet, OrderingFilter
from graphene import relay
from graphene.types.generic import GenericScalar
from graphene_django import DjangoObjectType

from apps.audit_logs import models

from .commons import TerrasoConnection


class AuditLogFilter(FilterSet):
    """
    LogFilter is a filter that filters logs and orders them by client_timestamp
    """

    class Meta:
        model = models.Log
        fields = [
            "client_timestamp",
            "user__id",
            "event",
            "resource_id",
            "resource_content_type__model",
            "resource_content_type",
        ]

    order_by = OrderingFilter(fields=(("client_timestamp", "client_timestamp"),))


class AuditLogNode(DjangoObjectType):
    """
    AuditLogNode is a node that represents an audit log
    """

    id = graphene.ID(source="pk", required=True)
    metadata = GenericScalar(required=True)
    resource_json_repr = GenericScalar(required=True)
    resource_content_type = graphene.String(required=True)

    class Meta:
        model = models.Log

        fields = (
            "client_timestamp",
            "user",
            "event",
            "resource_id",
        )

        interfaces = (relay.Node,)
        connection_class = TerrasoConnection
        filterset_class = AuditLogFilter

        def resolve_content_type(self, info):
            return self.resource_content_type.model
