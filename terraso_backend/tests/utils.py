import re

from jsonpath_ng import parse as jsonpath_parse

from apps.soil_id.models import (
    DepthDependentSoilData,
    DepthIntervalPreset,
    LandPKSIntervalDefaults,
    NRCSIntervalDefaults,
    ProjectSoilSettings,
    SoilData,
)


def match_json(match_expression, dictionary):
    return [match.value for match in jsonpath_parse(match_expression).find(dictionary)]


def to_snake_case(name):
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    name = re.sub("__([A-Z])", r"_\1", name)
    name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", name)
    return name.lower()


def site_intervals_match_project_preset(site):
    if (
        not hasattr(site, "soil_data")
        or not hasattr(site, "project")
        or not hasattr(site.project, "soil_settings")
    ):
        return (False, "Missing soil id")
    match site.project.soil_settings.depth_interval_preset:
        case DepthIntervalPreset.LANDPKS:
            intervals = LandPKSIntervalDefaults
        case DepthIntervalPreset.NRCS:
            intervals = NRCSIntervalDefaults
        case DepthIntervalPreset.CUSTOM:
            intervals = [
                {key: getattr(interval, key)}
                for key in ["depth_interval_start", "depth_interval_end"]
                for interval in site.project.soil_settings.depth_intervals
            ]
        case DepthIntervalPreset.NONE:
            # Nothing to test (for project)
            return True
        case _:
            assert False, "unkown preset " + site.project.depth_interval_preset
    for interval in intervals:
        if not site.soil_data.depth_intervals.filter(**interval).exists():
            assert False, "missing interval " + str(interval)
    return True


def add_soil_data_to_site(site, preset=DepthIntervalPreset.LANDPKS):
    project_soil_settings = ProjectSoilSettings.objects.create(
        project=site.project, depth_interval_preset=preset
    )
    SoilData.objects.create(site=site)
    for interval in LandPKSIntervalDefaults:
        DepthDependentSoilData.objects.create(
            soil_data=site.soil_data,
            depth_interval_start=interval["depth_interval_start"],
            depth_interval_end=interval["depth_interval_end"],
        )
    project_soil_settings.convert_site_intervals_to_preset(
        new_preset=project_soil_settings.depth_interval_preset, sites=[site]
    )
