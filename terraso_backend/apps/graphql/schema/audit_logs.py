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
