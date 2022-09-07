import graphene
import structlog
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import Membership
from apps.graphql.exceptions import GraphQLNotAllowedException
from apps.shared_data.models.data_entries import DataEntry
from apps.shared_data.models.visualization_config import VisualizationConfig

from ..exceptions import GraphQLNotFoundException
from .commons import BaseDeleteMutation, BaseWriteMutation, TerrasoConnection
from .constants import MutationTypes

logger = structlog.get_logger(__name__)


class VisualizationConfigNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = VisualizationConfig
        filter_fields = {
            "data_entry__groups__slug": ["exact", "icontains"],
        }
        fields = (
            "id",
            "configuration",
            "created_by",
            "created_at",
            "data_entry",
        )
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection

    @classmethod
    def get_queryset(cls, queryset, info):
        user_groups_ids = Membership.objects.filter(
            user=info.context.user, membership_status=Membership.APPROVED
        ).values_list("group", flat=True)
        return queryset.filter(data_entry__groups__in=user_groups_ids)


class VisualizationConfigAddMutation(BaseWriteMutation):
    visualization_config = graphene.Field(VisualizationConfigNode)

    model_class = VisualizationConfig

    class Input:
        configuration = graphene.JSONString()
        data_entry_id = graphene.ID(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user

        try:
            data_entry = DataEntry.objects.get(id=kwargs["data_entry_id"])
        except DataEntry.DoesNotExist:
            logger.error(
                "DataEntry not found when adding a VisualizationConfig",
                extra={"data_entry_id": kwargs["data_entry_id"]},
            )
            raise GraphQLNotFoundException(field="data_entry", model_name=Membership.__name__)

        kwargs["data_entry"] = data_entry

        if not cls.is_update(kwargs):
            kwargs["created_by"] = user

        return super().mutate_and_get_payload(root, info, **kwargs)


class VisualizationConfigUpdateMutation(BaseWriteMutation):
    visualization_config = graphene.Field(VisualizationConfigNode)

    model_class = VisualizationConfig

    class Input:
        id = graphene.ID(required=True)
        configuration = graphene.JSONString()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        visualization_config = VisualizationConfig.objects.get(pk=kwargs["id"])

        if not user.has_perm(VisualizationConfig.get_perm("change"), obj=visualization_config):
            logger.info(
                "Attempt to update a VisualizationConfig, but user lacks permission",
                extra={"user_id": user.pk, "data_entry_id": str(visualization_config.pk)},
            )
            raise GraphQLNotAllowedException(
                model_name=VisualizationConfig.__name__, operation=MutationTypes.UPDATE
            )

        return super().mutate_and_get_payload(root, info, **kwargs)


class VisualizationConfigDeleteMutation(BaseDeleteMutation):
    visualization_config = graphene.Field(VisualizationConfigNode)

    model_class = VisualizationConfig

    class Input:
        id = graphene.ID()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        visualization_config = VisualizationConfig.objects.get(pk=kwargs["id"])

        if not user.has_perm(VisualizationConfig.get_perm("delete"), obj=visualization_config):
            logger.info(
                "Attempt to delete a VisualizationConfig, but user lacks permission",
                extra={"user_id": user.pk, "data_entry_id": str(visualization_config.pk)},
            )
            raise GraphQLNotAllowedException(
                model_name=VisualizationConfig.__name__, operation=MutationTypes.DELETE
            )
        return super().mutate_and_get_payload(root, info, **kwargs)
