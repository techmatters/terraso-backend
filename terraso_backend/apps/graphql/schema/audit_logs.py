import graphene
from django_filters import FilterSet, OrderingFilter
from graphene import relay
from graphene.types.generic import GenericScalar
from graphene_django import DjangoObjectType

from apps.audit_logs import models

from .commons import TerrasoConnection


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
            "metadata",
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
            "resource_content_type",
        ]

    order_by = OrderingFilter(fields=(("client_timestamp", "client_timestamp"),))
