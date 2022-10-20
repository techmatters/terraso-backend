import graphene
import structlog
from django.db import transaction
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import Landscape, LandscapeDevelopmentStrategy, TaxonomyTerm
from apps.graphql.exceptions import GraphQLNotAllowedException

from .commons import BaseDeleteMutation, BaseWriteMutation, TerrasoConnection
from .constants import MutationTypes

logger = structlog.get_logger(__name__)


class LandscapeNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)
    area_types = graphene.List(graphene.String)

    class Meta:
        model = Landscape
        filter_fields = {
            "name": ["icontains"],
            "description": ["icontains"],
            "slug": ["exact", "icontains"],
            "website": ["icontains"],
            "location": ["icontains"],
        }
        fields = (
            "name",
            "slug",
            "description",
            "website",
            "location",
            "area_polygon",
            "created_by",
            "associated_groups",
            "population",
            "development_strategy",
            "taxonomy_terms",
        )
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection


class LandscapeDevelopmentStrategyNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = LandscapeDevelopmentStrategy
        fields = (
            "objectives",
            "problem_situtation",
            "problem_situtation",
            "other_information",
        )
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection


def set_landscape_taxonomy_terms(landscape, kwargs):
    if "taxonomy_type_terms" in kwargs:
        taxonomy_type_terms = kwargs.pop("taxonomy_type_terms")
        taxonomy_terms = [
            TaxonomyTerm.objects.get_or_create(
                value_original=input_term["valueOriginal"],
                value_es=input_term["valueEs"],
                value_en=input_term["valueEn"],
                type=input_term["type"],
            )[0]
            for type in taxonomy_type_terms
            for input_term in taxonomy_type_terms[type]
        ]

        landscape.taxonomy_terms.set(taxonomy_terms)


class LandscapeAddMutation(BaseWriteMutation):
    landscape = graphene.Field(LandscapeNode)

    model_class = Landscape

    class Input:
        name = graphene.String(required=True)
        description = graphene.String()
        website = graphene.String()
        location = graphene.String()
        area_polygon = graphene.JSONString()
        area_types = graphene.JSONString()
        population = graphene.Int()
        taxonomy_type_terms = graphene.JSONString()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        with transaction.atomic():
            user = info.context.user

            if not cls.is_update(kwargs):
                kwargs["created_by"] = user

            result = super().mutate_and_get_payload(root, info, **kwargs)

            set_landscape_taxonomy_terms(result.landscape, kwargs)

            return cls(landscape=result.landscape)


class LandscapeUpdateMutation(BaseWriteMutation):
    landscape = graphene.Field(LandscapeNode)

    model_class = Landscape

    class Input:
        id = graphene.ID(required=True)
        name = graphene.String()
        description = graphene.String()
        website = graphene.String()
        location = graphene.String()
        area_polygon = graphene.JSONString()
        area_types = graphene.JSONString()
        population = graphene.Int()
        taxonomy_type_terms = graphene.JSONString()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        landscape_id = kwargs["id"]

        if not user.has_perm(Landscape.get_perm("change"), obj=landscape_id):
            logger.info(
                "Attempt to update a Landscape, but user has no permission",
                extra={"user_id": user.pk, "landscape_id": landscape_id},
            )
            raise GraphQLNotAllowedException(
                model_name=Landscape.__name__, operation=MutationTypes.UPDATE
            )

        result = super().mutate_and_get_payload(root, info, **kwargs)

        set_landscape_taxonomy_terms(result.landscape, kwargs)

        return result


class LandscapeDeleteMutation(BaseDeleteMutation):
    landscape = graphene.Field(LandscapeNode)

    model_class = Landscape

    class Input:
        id = graphene.ID()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        landscape_id = kwargs["id"]

        if not user.has_perm(Landscape.get_perm("delete"), obj=landscape_id):
            logger.info(
                "Attempt to delete a Landscape, but user has no permission",
                extra={"user_id": user.pk, "landscape_id": landscape_id},
            )
            raise GraphQLNotAllowedException(
                model_name=Landscape.__name__, operation=MutationTypes.DELETE
            )
        return super().mutate_and_get_payload(root, info, **kwargs)
