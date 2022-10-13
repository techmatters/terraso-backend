import graphene
import structlog
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import TaxonomyTerm

from .commons import TerrasoConnection

logger = structlog.get_logger(__name__)


class TaxonomyTermNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = TaxonomyTerm
        filter_fields = {
            "name": ["icontains"],
            "type": ["icontains"],
        }
        fields = (
            "name",
            "type",
            "slug",
        )
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection
