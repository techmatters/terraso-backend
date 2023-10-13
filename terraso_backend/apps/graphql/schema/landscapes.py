# Copyright © 2021-2023 Technology Matters
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
import structlog
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.gis.utils import m2_to_hectares
from apps.core.models import (
    Group,
    Landscape,
    LandscapeDevelopmentStrategy,
    LandscapeGroup,
    Membership,
    TaxonomyTerm,
)
from apps.graphql.exceptions import GraphQLNotAllowedException

from .commons import BaseDeleteMutation, BaseWriteMutation, TerrasoConnection
from .constants import MutationTypes
from .gis import Point

logger = structlog.get_logger(__name__)


class LandscapeNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)
    area_types = graphene.List(graphene.String)
    default_group = graphene.Field("apps.graphql.schema.groups.GroupNode")
    center_coordinates = graphene.Field(Point)
    shared_resources = graphene.List("apps.graphql.schema.shared_resources.SharedResourceNode")

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
            "email",
            "area_scalar_m2",
            "created_by",
            "associated_groups",
            "population",
            "associated_development_strategy",
            "taxonomy_terms",
            "partnership_status",
            "profile_image",
            "profile_image_description",
            "center_coordinates",
        )

        interfaces = (relay.Node,)
        connection_class = TerrasoConnection

    area_scalar_ha = graphene.Float()

    @classmethod
    def get_queryset(cls, queryset, info):
        is_anonymous = info.context.user.is_anonymous

        try:
            # Prefetch default landscape group, account membership and count of members
            group_queryset = (
                Group.objects.prefetch_related(
                    Prefetch(
                        "memberships",
                        to_attr="account_memberships",
                        queryset=Membership.objects.filter(
                            user=info.context.user,
                        ),
                    ),
                )
                if not is_anonymous
                else Group.objects.all()
            ).annotate(
                memberships_count=Count(
                    "memberships__user",
                    distinct=True,
                    filter=Q(memberships__deleted_at__isnull=True)
                    & Q(memberships__membership_status=Membership.APPROVED),
                )
            )
            landscape_group_queryset = LandscapeGroup.objects.prefetch_related(
                Prefetch(
                    "group",
                    queryset=group_queryset,
                ),
            ).filter(is_default_landscape_group=True)
            # Fetch all fields from Landscape, except for area_polygon
            result = (
                queryset.defer("area_polygon")
                .prefetch_related(
                    Prefetch(
                        "associated_groups",
                        to_attr="default_landscape_groups",
                        queryset=landscape_group_queryset,
                    )
                )
                .all()
            )
        except Exception as e:
            logger.exception("Error prefetching Landscape data", error=e)
            raise e
        return result

    def resolve_area_scalar_ha(self, info):
        area = self.area_scalar_m2
        return None if area is None else round(m2_to_hectares(area), 3)

    def resolve_default_group(self, info):
        if hasattr(self, "default_landscape_groups"):
            if len(self.default_landscape_groups) > 0:
                return self.default_landscape_groups[0].group
            return None
        return self.get_default_group()

    def resolve_shared_resources(self, info, **kwargs):
        return self.shared_resources.all()


class LandscapeDevelopmentStrategyNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = LandscapeDevelopmentStrategy
        fields = (
            "objectives",
            "opportunities",
            "problem_situtation",
            "intervention_strategy",
        )
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection


def set_landscape_taxonomy_terms(landscape, taxonomy_type_terms):
    if taxonomy_type_terms is not None:
        taxonomy_terms = [
            TaxonomyTerm.objects.get_or_create(
                value_original=input_term["valueOriginal"],
                value_es=input_term.get("valueEs", ""),
                value_en=input_term.get("valueEn", ""),
                type=input_term["type"],
            )[0]
            for type in taxonomy_type_terms
            for input_term in taxonomy_type_terms[type]
        ]

        landscape.taxonomy_terms.set(taxonomy_terms)


def set_landscape_groups(landscape, group_associations):
    if group_associations is not None:
        LandscapeGroup.objects.filter(
            landscape=landscape, is_default_landscape_group=False
        ).delete()
        for group_association in group_associations:
            group = Group.objects.get(slug=group_association["slug"])
            landscape_group = LandscapeGroup(
                group=group, landscape=landscape, is_default_landscape_group=False
            )
            if "isPartnership" in group_association:
                landscape_group.is_partnership = group_association["isPartnership"]
            if "partnershipYear" in group_association:
                landscape_group.partnership_year = group_association["partnershipYear"]
            landscape_group.save()


def set_landscape_development_strategy(landscape, development_strategy_input):
    if development_strategy_input is not None:
        LandscapeDevelopmentStrategy.objects.filter(landscape=landscape).delete()
        development_strategy = LandscapeDevelopmentStrategy(
            objectives=development_strategy_input["objectives"],
            opportunities=development_strategy_input["opportunities"],
            problem_situtation=development_strategy_input["problemSitutation"],
            intervention_strategy=development_strategy_input["interventionStrategy"],
            landscape=landscape,
        )
        development_strategy.save()


class LandscapeAddMutation(BaseWriteMutation):
    landscape = graphene.Field(LandscapeNode)

    model_class = Landscape

    class Input:
        name = graphene.String(required=True)
        description = graphene.String()
        website = graphene.String()
        location = graphene.String()
        area_polygon = graphene.JSONString()
        email = graphene.String()
        area_types = graphene.JSONString()
        population = graphene.Int()
        taxonomy_type_terms = graphene.JSONString()
        partnership_status = graphene.String()
        group_associations = graphene.JSONString()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        with transaction.atomic():
            user = info.context.user

            if not cls.is_update(kwargs):
                kwargs["created_by"] = user

            taxonomy_type_terms = (
                kwargs.pop("taxonomy_type_terms") if "taxonomy_type_terms" in kwargs else None
            )
            group_associations = (
                kwargs.pop("group_associations") if "group_associations" in kwargs else None
            )

            result = super().mutate_and_get_payload(root, info, **kwargs)

            set_landscape_taxonomy_terms(result.landscape, taxonomy_type_terms)
            set_landscape_groups(result.landscape, group_associations)

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
        email = graphene.String()
        area_types = graphene.JSONString()
        population = graphene.Int()
        taxonomy_type_terms = graphene.JSONString()
        partnership_status = graphene.String()
        group_associations = graphene.JSONString()
        development_strategy = graphene.JSONString()
        profile_image = graphene.String()
        profile_image_description = graphene.String()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        with transaction.atomic():
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

            taxonomy_type_terms = (
                kwargs.pop("taxonomy_type_terms") if "taxonomy_type_terms" in kwargs else None
            )
            group_associations = (
                kwargs.pop("group_associations") if "group_associations" in kwargs else None
            )
            development_strategy_input = (
                kwargs.pop("development_strategy") if "development_strategy" in kwargs else None
            )

            result = super().mutate_and_get_payload(root, info, **kwargs)

            set_landscape_taxonomy_terms(result.landscape, taxonomy_type_terms)
            set_landscape_groups(result.landscape, group_associations)
            set_landscape_development_strategy(result.landscape, development_strategy_input)

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
