import graphene
import structlog
from graphene_django import DjangoObjectType

from apps.graphql.schema.constants import MutationTypes
from apps.project_management.models.sites import Site
from apps.soil_id.models.soil_data import SoilData

from .commons import BaseWriteMutation

logger = structlog.get_logger(__name__)
logger.info("here")


class SoilDataNode(DjangoObjectType):
    class Meta:
        model = SoilData
        fields = "__all__"  # exclude IDs


class SoilDataUpdateMutation(BaseWriteMutation):
    soil_data = graphene.Field(SoilDataNode)
    model_class = SoilData

    class Input:
        site_id = graphene.ID(required=True)
        down_slope = graphene.Int()
        cross_slope = graphene.Int()
        bedrock = graphene.Int()
        slope_landscape_position = graphene.String()
        slope_aspect = graphene.Int()
        slope_steepness_select = graphene.String()
        slope_steepness_percent = graphene.Int()
        slope_steepness_degree = graphene.Int()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        print("BEGINNING")
        user = info.context.user
        site = Site.objects.get(id=kwargs["site_id"])
        if not user.has_perm(Site.get_perm("change"), site):
            raise cls.not_allowed(MutationTypes.UPDATE)
        if site.soil_data is None:
            site.soil_data = SoilData()
        kwargs["model_instance"] = site.soil_data
        results = super().mutate_and_get_payload(root, info, **kwargs)
        logger.info("TESTING")
        return results
