import graphene
from graphene_django import DjangoObjectType
from graphene import relay
from django_filters import FilterSet, OrderingFilter
from graphene.types.generic import GenericScalar # Solution

from .commons import TerrasoConnection

from apps.audit_logs import models


class AuditLogNode(DjangoObjectType):
    """
    AuditLogNode is a node that represents an audit log
    """
    id = graphene.ID(source="pk", required=True)
    metadata = GenericScalar()
    resource_json_repr = GenericScalar()
    resource_content_type = graphene.String()

    class Meta:
        model = models.Log

        fields = (
            "client_timestamp",
            "user",
            "event",
            "resource_id",
            "resource_content_type",
            "metadata"
        )

        interfaces = (relay.Node,)
        connection_class = TerrasoConnection

        def resolve_content_type(self, info):
            d = self.resource_content_type.model
            return d


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
            "resource_content_type"
        ]

    order_by = OrderingFilter(
        fields=(
            ("client_timestamp", "client_timestamp"),
        )
    )
