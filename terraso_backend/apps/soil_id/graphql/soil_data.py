import graphene
from django.db import transaction
from graphene_django import DjangoObjectType

from apps.graphql.schema.commons import BaseWriteMutation
from apps.graphql.schema.constants import MutationTypes
from apps.project_management.models.sites import Site
from apps.soil_id.models.depth_dependent_soil_data import DepthDependentSoilData
from apps.soil_id.models.soil_data import SoilData


class DepthInterval(graphene.ObjectType):
    start = graphene.Int(required=True)
    end = graphene.Int(required=True)


class SoilDataNode(DjangoObjectType):
    depth_intervals = graphene.List(graphene.NonNull(DepthInterval), required=True)

    class Meta:
        model = SoilData
        exclude = ["deleted_at", "deleted_by_cascade", "id", "created_at", "updated_at", "site"]

    @classmethod
    def down_slope_enum(cls):
        return cls._meta.fields["down_slope"].type()

    @classmethod
    def cross_slope_enum(cls):
        return cls._meta.fields["cross_slope"].type()

    @classmethod
    def slope_landscape_position_enum(cls):
        return cls._meta.fields["slope_landscape_position"].type()

    @classmethod
    def slope_steepness_enum(cls):
        return cls._meta.fields["slope_steepness_select"].type()


class DepthDependentSoilDataNode(DjangoObjectType):
    class Meta:
        model = DepthDependentSoilData
        exclude = [
            "deleted_at",
            "deleted_by_cascade",
            "id",
            "created_at",
            "updated_at",
            "soil_data",
        ]

    @classmethod
    def texture_enum(cls):
        return cls._meta.fields["texture"].type()

    @classmethod
    def rock_fragment_volume_enum(cls):
        return cls._meta.fields["rock_fragment_volume"].type()

    @classmethod
    def color_hue_substep_enum(cls):
        return cls._meta.fields["color_hue_substep"].type()

    @classmethod
    def color_hue_enum(cls):
        return cls._meta.fields["color_hue"].type()

    @classmethod
    def color_value_enum(cls):
        return cls._meta.fields["color_value"].type()

    @classmethod
    def color_chroma_enum(cls):
        return cls._meta.fields["color_chroma"].type()

    @classmethod
    def conductivity_test_enum(cls):
        return cls._meta.fields["conductivity_test"].type()

    @classmethod
    def conductivity_unit_enum(cls):
        return cls._meta.fields["conductivity_unit"].type()

    @classmethod
    def structure_enum(cls):
        return cls._meta.fields["structure"].type()

    @classmethod
    def ph_testing_solution_enum(cls):
        return cls._meta.fields["ph_testing_solution"].type()

    @classmethod
    def ph_testing_method_enum(cls):
        return cls._meta.fields["ph_testing_method"].type()

    @classmethod
    def soil_organic_carbon_testing_enum(cls):
        return cls._meta.fields["soil_organic_carbon_testing"].type()

    @classmethod
    def soil_organic_matter_testing_enum(cls):
        return cls._meta.fields["soil_organic_matter_testing"].type()

    @classmethod
    def carbonates_enum(cls):
        return cls._meta.fields["carbonates"].type()


class DepthIntervalInput(graphene.InputObjectType):
    start = graphene.Int(required=True)
    end = graphene.Int(required=True)


class SoilDataUpdateMutation(BaseWriteMutation):
    soil_data = graphene.Field(SoilDataNode)
    model_class = SoilData

    class Input:
        site_id = graphene.ID(required=True)
        down_slope = SoilDataNode.down_slope_enum()
        cross_slope = SoilDataNode.cross_slope_enum()
        bedrock = graphene.Int()
        slope_landscape_position = SoilDataNode.slope_landscape_position_enum()
        slope_aspect = graphene.Int()
        slope_steepness_select = SoilDataNode.slope_steepness_enum()
        slope_steepness_percent = graphene.Int()
        slope_steepness_degree = graphene.Int()
        depth_intervals = graphene.List(graphene.NonNull(DepthIntervalInput))

    @classmethod
    def mutate_and_get_payload(cls, root, info, site_id, **kwargs):
        site = cls.get_or_throw(Site, "id", site_id)

        user = info.context.user
        if not user.has_perm(Site.get_perm("change"), site):
            raise cls.not_allowed(MutationTypes.UPDATE)

        if not hasattr(site, "soil_data"):
            site.soil_data = SoilData()

        kwargs["model_instance"] = site.soil_data

        return super().mutate_and_get_payload(root, info, **kwargs)


class DepthDependentSoilDataUpdateMutation(BaseWriteMutation):
    depth_dependent_soil_data = graphene.Field(DepthDependentSoilDataNode)
    model_class = DepthDependentSoilData

    class Input:
        site_id = graphene.ID(required=True)
        depth_start = graphene.Int(required=True)
        depth_end = graphene.Int(required=True)
        texture = DepthDependentSoilDataNode.texture_enum()
        rock_fragment_volume = DepthDependentSoilDataNode.rock_fragment_volume_enum()
        color_hue_substep = DepthDependentSoilDataNode.color_hue_substep_enum()
        color_hue = DepthDependentSoilDataNode.color_hue_enum()
        color_value = DepthDependentSoilDataNode.color_value_enum()
        color_chroma = DepthDependentSoilDataNode.color_chroma_enum()
        conductivity = graphene.Decimal()
        conductivity_test = DepthDependentSoilDataNode.conductivity_test_enum()
        conductivity_unit = DepthDependentSoilDataNode.conductivity_unit_enum()
        structure = DepthDependentSoilDataNode.structure_enum()
        ph = graphene.Decimal()
        ph_testing_solution = DepthDependentSoilDataNode.ph_testing_solution_enum()
        ph_testing_method = DepthDependentSoilDataNode.ph_testing_method_enum()
        soil_organic_carbon = graphene.Decimal()
        soil_organic_matter = graphene.Decimal()
        soil_organic_carbon_testing = DepthDependentSoilDataNode.soil_organic_carbon_testing_enum()
        soil_organic_matter_testing = DepthDependentSoilDataNode.soil_organic_matter_testing_enum()
        sodium_absorption_ratio = graphene.Decimal()
        carbonates = DepthDependentSoilDataNode.carbonates_enum()

    @classmethod
    def mutate_and_get_payload(cls, root, info, site_id, depth_start, depth_end, **kwargs):
        site = cls.get_or_throw(Site, "id", site_id)

        user = info.context.user
        if not user.has_perm(Site.get_perm("change"), site):
            raise cls.not_allowed(MutationTypes.UPDATE)

        with transaction.atomic():
            if not hasattr(site, "soil_data"):
                site.soil_data = SoilData()
                site.soil_data.save()

            kwargs["model_instance"], _ = site.soil_data.depth_dependent_data.get_or_create(
                depth_start=depth_start, depth_end=depth_end
            )

            return super().mutate_and_get_payload(root, info, **kwargs)
