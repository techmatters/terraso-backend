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
    @classmethod
    def slope_enum(cls):
        return cls._meta.fields["down_slope"].type


class SoilDataUpdateMutation(BaseWriteMutation):
    soil_data = graphene.Field(SoilDataNode)
    model_class = SoilData

    class Input:
        site_id = graphene.ID(required=True)
        down_slope = SoilDataNode.slope_enum()
        cross_slope = SoilDataNode.slope_enum()
        bedrock = graphene.Int(blank=True)
        slope_landscape_position = graphene.String(blank=True)
        slope_aspect = graphene.Int(blank=True)
        slope_steepness_select = graphene.String(blank=True)
        slope_steepness_percent = graphene.Int(blank=True)
        slope_steepness_degree = graphene.Int(blank=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        site = cls.get_or_throw(Site, "id", kwargs.pop("site_id"))
        if not user.has_perm(Site.get_perm("change"), site):
            raise cls.not_allowed(MutationTypes.UPDATE)
        if not hasattr(site, "soil_data"):
            site.soil_data = SoilData()
        if "down_slope" in kwargs:
            kwargs["down_slope"] = kwargs["down_slope"].value
        kwargs["model_instance"] = site.soil_data
        results = super().mutate_and_get_payload(root, info, **kwargs)
        return results
