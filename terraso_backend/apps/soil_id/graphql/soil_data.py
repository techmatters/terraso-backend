import graphene
from django.db import transaction
from graphene_django import DjangoObjectType

from apps.graphql.schema.commons import (
    BaseAuthenticatedMutation,
    BaseWriteMutation,
    data_model_excluded_fields,
)
from apps.graphql.schema.constants import MutationTypes
from apps.graphql.schema.sites import SiteNode
from apps.project_management.graphql.projects import ProjectNode
from apps.project_management.models.projects import Project
from apps.project_management.models.sites import Site
from apps.soil_id.models.depth_dependent_soil_data import DepthDependentSoilData
from apps.soil_id.models.project_soil_settings import (
    ProjectDepthInterval,
    ProjectSoilSettings,
)
from apps.soil_id.models.soil_data import SoilData, SoilDataDepthInterval


class DepthInterval(graphene.ObjectType):
    start = graphene.Int(required=True)
    end = graphene.Int(required=True)


class SoilDataDepthIntervalNode(DjangoObjectType):
    site = graphene.Field(SiteNode, source="soil_data__site", required=True)
    depth_interval = graphene.Field(DepthInterval, required=True)

    class Meta:
        model = SoilDataDepthInterval
        exclude = data_model_excluded_fields() + [
            "soil_data",
            "depth_interval_start",
            "depth_interval_end",
        ]

    def resolve_depth_interval(self, info):
        return DepthInterval(start=self.depth_interval_start, end=self.depth_interval_end)


class SoilDataNode(DjangoObjectType):
    class Meta:
        model = SoilData
        exclude = data_model_excluded_fields()

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

    @classmethod
    def surface_cracks_enum(cls):
        return cls._meta.fields["surface_cracks_select"].type()

    @classmethod
    def surface_salt_enum(cls):
        return cls._meta.fields["surface_salt_select"].type()

    @classmethod
    def flooding_enum(cls):
        return cls._meta.fields["flooding_select"].type()

    @classmethod
    def lime_requirements_enum(cls):
        return cls._meta.fields["lime_requirements_select"].type()

    @classmethod
    def surface_stoniness_enum(cls):
        return cls._meta.fields["surface_stoniness_select"].type()

    @classmethod
    def water_table_depth_enum(cls):
        return cls._meta.fields["water_table_depth_select"].type()

    @classmethod
    def soil_depth_enum(cls):
        return cls._meta.fields["soil_depth_select"].type()

    @classmethod
    def land_cover_enum(cls):
        return cls._meta.fields["land_cover_select"].type()

    @classmethod
    def grazing_enum(cls):
        return cls._meta.fields["grazing_select"].type()


class ProjectSoilSettingsNode(DjangoObjectType):
    class Meta:
        model = ProjectSoilSettings
        exclude = [
            "deleted_at",
            "deleted_by_cascade",
            "id",
            "created_at",
            "updated_at",
        ]

    @classmethod
    def measurement_units_enum(cls):
        return cls._meta.fields["measurement_units"].type()

    @classmethod
    def depth_interval_preset_enum(cls):
        return cls._meta.fields["depth_interval_preset"].type.of_type()


class ProjectDepthIntervalNode(DjangoObjectType):
    project = graphene.Field(ProjectNode, source="project__project", required=True)
    depth_interval = graphene.Field(DepthInterval, required=True)

    class Meta:
        model = ProjectDepthInterval
        exclude = data_model_excluded_fields() + [
            "depth_interval_start",
            "depth_interval_end",
        ]

    def resolve_depth_interval(self, info):
        return DepthInterval(start=self.depth_interval_start, end=self.depth_interval_end)


class DepthDependentSoilDataNode(DjangoObjectType):
    site = graphene.Field(SiteNode, source="soil_data__site", required=True)
    depth_interval = graphene.Field(DepthInterval, required=True)

    class Meta:
        model = DepthDependentSoilData
        exclude = data_model_excluded_fields() + [
            "soil_data",
            "depth_interval_start",
            "depth_interval_end",
        ]

    def resolve_depth_interval(self, info):
        return DepthInterval(start=self.depth_interval_start, end=self.depth_interval_end)

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


class SoilDataUpdateDepthIntervalMutation(BaseWriteMutation):
    soil_data = graphene.Field(SoilDataNode)
    model_class = SoilDataDepthIntervalNode
    result_class = SoilData

    class Input:
        site_id = graphene.ID(required=True)
        label = graphene.String()
        depth_interval = graphene.Field(DepthIntervalInput, required=True)
        soil_texture_enabled = graphene.Boolean()
        soil_color_enabled = graphene.Boolean()
        carbonates_enabled = graphene.Boolean()
        ph_enabled = graphene.Boolean()
        soil_organic_carbon_matter_enabled = graphene.Boolean()
        electrical_conductivity_enabled = graphene.Boolean()
        sodium_adsorption_ratio_enabled = graphene.Boolean()
        soil_structure_enabled = graphene.Boolean()

    @classmethod
    def mutate_and_get_payload(cls, root, info, site_id, depth_interval, **kwargs):
        site = cls.get_or_throw(Site, "id", site_id)

        user = info.context.user
        if not user.has_perm(Site.get_perm("change"), site):
            raise cls.not_allowed(MutationTypes.UPDATE)

        with transaction.atomic():
            if not hasattr(site, "soil_data"):
                site.soil_data = SoilData()
                site.soil_data.save()

            kwargs["model_instance"], _ = site.soil_data.depth_intervals.get_or_create(
                depth_interval_start=depth_interval["start"],
                depth_interval_end=depth_interval["end"],
            )

            return super().mutate_and_get_payload(
                root, info, result_instance=site.soil_data, **kwargs
            )


class SoilDataDeleteDepthIntervalMutation(BaseAuthenticatedMutation):
    soil_data = graphene.Field(SoilDataNode)

    class Input:
        site_id = graphene.ID(required=True)
        depth_interval = graphene.Field(DepthIntervalInput, required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, site_id, depth_interval, **kwargs):
        site = cls.get_or_throw(Site, "id", site_id)

        user = info.context.user
        if not user.has_perm(Site.get_perm("delete"), site):
            raise cls.not_allowed(MutationTypes.DELETE)

        if not hasattr(site, "soil_data"):
            cls.not_found()

        try:
            depth_interval = site.soil_data.depth_intervals.get(
                depth_interval_start=depth_interval["start"],
                depth_interval_end=depth_interval["end"],
            )
        except SoilDataDepthInterval.DoesNotExist:
            cls.not_found()

        depth_interval.delete()

        return SoilDataDeleteDepthIntervalMutation(soil_data=site.soil_data)


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
        surface_cracks_select = SoilDataNode.surface_cracks_enum()
        surface_salt_select = SoilDataNode.surface_salt_enum()
        flooding_select = SoilDataNode.flooding_enum()
        lime_requirements_select = SoilDataNode.lime_requirements_enum()
        surface_stoniness_select = SoilDataNode.surface_stoniness_enum()
        water_table_depth_select = SoilDataNode.water_table_depth_enum()
        soil_depth_select = SoilDataNode.soil_depth_enum()
        land_cover_select = SoilDataNode.land_cover_enum()
        grazing_select = SoilDataNode.grazing_enum()

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
    soil_data = graphene.Field(SoilDataNode)
    model_class = DepthDependentSoilData
    result_class = SoilData

    class Input:
        site_id = graphene.ID(required=True)
        depth_interval = graphene.Field(DepthIntervalInput, required=True)
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
    def mutate_and_get_payload(cls, root, info, site_id, depth_interval, **kwargs):
        site = cls.get_or_throw(Site, "id", site_id)

        user = info.context.user
        if not user.has_perm(Site.get_perm("change"), site):
            raise cls.not_allowed(MutationTypes.UPDATE)

        with transaction.atomic():
            if not hasattr(site, "soil_data"):
                site.soil_data = SoilData()
                site.soil_data.save()

            kwargs["model_instance"], _ = site.soil_data.depth_dependent_data.get_or_create(
                depth_interval_start=depth_interval["start"],
                depth_interval_end=depth_interval["end"],
            )

            return super().mutate_and_get_payload(
                root, info, result_instance=site.soil_data, **kwargs
            )


class ProjectSoilSettingsUpdateMutation(BaseWriteMutation):
    project_soil_settings = graphene.Field(ProjectSoilSettingsNode)
    model_class = ProjectSoilSettings

    class Input:
        project_id = graphene.ID(required=True)
        measurement_units = ProjectSoilSettingsNode.measurement_units_enum()
        depth_interval_preset = ProjectSoilSettingsNode.depth_interval_preset_enum()
        soil_pit_required = graphene.Boolean()
        slope_required = graphene.Boolean()
        soil_texture_required = graphene.Boolean()
        soil_color_required = graphene.Boolean()
        vertical_cracking_required = graphene.Boolean()
        carbonates_required = graphene.Boolean()
        ph_required = graphene.Boolean()
        soil_organic_carbon_matter_required = graphene.Boolean()
        electrical_conductivity_required = graphene.Boolean()
        sodium_adsorption_ratio_required = graphene.Boolean()
        soil_structure_required = graphene.Boolean()
        land_use_land_cover_required = graphene.Boolean()
        soil_limitations_required = graphene.Boolean()
        photos_required = graphene.Boolean()
        notes_required = graphene.Boolean()

    @classmethod
    def mutate_and_get_payload(cls, root, info, project_id, **kwargs):
        project = cls.get_or_throw(Project, "id", project_id)

        user = info.context.user
        if not user.has_perm(Project.get_perm("change"), project):
            raise cls.not_allowed(MutationTypes.UPDATE)

        if not hasattr(project, "soil_settings"):
            project.soil_settings = ProjectSoilSettings()

        kwargs["model_instance"] = project.soil_settings

        return super().mutate_and_get_payload(root, info, **kwargs)


class ProjectSoilSettingsUpdateDepthIntervalMutation(BaseWriteMutation):
    project_soil_settings = graphene.Field(ProjectSoilSettingsNode)
    model_class = ProjectDepthInterval
    result_class = ProjectSoilSettings

    class Input:
        project_id = graphene.ID(required=True)
        label = graphene.String()
        depth_interval = graphene.Field(DepthIntervalInput, required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, project_id, depth_interval, **kwargs):
        project = cls.get_or_throw(Project, "id", project_id)

        user = info.context.user
        if not user.has_perm(Project.get_perm("change"), project):
            raise cls.not_allowed(MutationTypes.UPDATE)

        with transaction.atomic():
            if not hasattr(project, "soil_settings"):
                project.soil_settings = ProjectSoilSettings()
                project.soil_settings.save()

            kwargs["model_instance"], _ = project.soil_settings.depth_intervals.get_or_create(
                depth_interval_start=depth_interval["start"],
                depth_interval_end=depth_interval["end"],
            )

            return super().mutate_and_get_payload(
                root, info, result_instance=project.soil_settings, **kwargs
            )


class ProjectSoilSettingsDeleteDepthIntervalMutation(BaseAuthenticatedMutation):
    project_soil_settings = graphene.Field(ProjectSoilSettingsNode)

    class Input:
        project_id = graphene.ID(required=True)
        depth_interval = graphene.Field(DepthIntervalInput, required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, project_id, depth_interval, **kwargs):
        project = cls.get_or_throw(Project, "id", project_id)

        user = info.context.user
        if not user.has_perm(Project.get_perm("delete"), project):
            raise cls.not_allowed(MutationTypes.DELETE)

        if not hasattr(project, "soil_settings"):
            cls.not_found()

        try:
            depth_interval = project.soil_settings.depth_intervals.get(
                depth_interval_start=depth_interval["start"],
                depth_interval_end=depth_interval["end"],
            )
        except ProjectDepthInterval.DoesNotExist:
            cls.not_found()

        depth_interval.delete()
        return ProjectSoilSettingsDeleteDepthIntervalMutation(
            project_soil_settings=project.soil_settings
        )
