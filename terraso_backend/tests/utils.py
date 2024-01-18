import re

from jsonpath_ng import parse as jsonpath_parse

from apps.soil_id.models import (
    DepthDependentSoilData,
    DepthIntervalPreset,
    LandPKSIntervalDefaults,
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


def add_soil_data_to_site(site, preset=DepthIntervalPreset.LANDPKS):
    ProjectSoilSettings.objects.create(project=site.project, depth_interval_preset=preset)
    if not getattr(site, "soil_data", None):
        SoilData.objects.create(site=site)
    for interval in LandPKSIntervalDefaults:
        DepthDependentSoilData.objects.create(
            soil_data=site.soil_data,
            depth_interval_start=interval["depth_interval_start"],
            depth_interval_end=interval["depth_interval_end"],
        )
