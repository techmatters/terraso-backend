import graphene
import structlog
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import Membership
from apps.graphql.exceptions import GraphQLNotAllowedException
from apps.shared_data.models import DataEntry

from .commons import BaseDeleteMutation, BaseWriteMutation, TerrasoConnection
from .constants import MutationTypes

logger = structlog.get_logger(__name__)


class DataEntryNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = DataEntry
        filter_fields = {
            "name": ["icontains"],
            "description": ["icontains"],
            "url": ["icontains"],
            "resource_type": ["in"],
            "groups__slug": ["exact", "icontains"],
            "groups__id": ["exact"],
        }
        fields = (
            "name",
            "description",
            "resource_type",
            "url",
            "size",
            "created_by",
            "created_at",
            "groups",
            "visualizations",
        )
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection

    @classmethod
    def get_queryset(cls, queryset, info):
        user_groups_ids = Membership.objects.filter(
            user=info.context.user, membership_status=Membership.APPROVED
        ).values_list("group", flat=True)
        return queryset.filter(groups__in=user_groups_ids)

    def resolve_url(self, info):
        return self.signed_url


class DataEntryUpdateMutation(BaseWriteMutation):
    data_entry = graphene.Field(DataEntryNode)

    model_class = DataEntry

    class Input:
        id = graphene.ID(required=True)
        name = graphene.String()
        description = graphene.String()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        data_entry = DataEntry.objects.get(pk=kwargs["id"])

        if not user.has_perm(DataEntry.get_perm("change"), obj=data_entry):
            logger.info(
                "Attempt to update a DataEntry, but user lacks permission",
                extra={"user_id": user.pk, "data_entry_id": str(data_entry.pk)},
            )
            raise GraphQLNotAllowedException(
                model_name=DataEntry.__name__, operation=MutationTypes.UPDATE
            )

        return super().mutate_and_get_payload(root, info, **kwargs)


class DataEntryDeleteMutation(BaseDeleteMutation):
    data_entry = graphene.Field(DataEntryNode)

    model_class = DataEntry

    class Input:
        id = graphene.ID()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        data_entry = DataEntry.objects.get(pk=kwargs["id"])

        if not user.has_perm(DataEntry.get_perm("delete"), obj=data_entry):
            logger.info(
                "Attempt to delete a DataEntry, but user lacks permission",
                extra={"user_id": user.pk, "data_entry_id": str(data_entry.pk)},
            )
            raise GraphQLNotAllowedException(
                model_name=DataEntry.__name__, operation=MutationTypes.DELETE
            )
        return super().mutate_and_get_payload(root, info, **kwargs)
