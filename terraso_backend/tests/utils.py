# Copyright © 2024 Technology Matters
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

import re

from jsonpath_ng import parse as jsonpath_parse

from apps.soil_id.models import (
    DepthDependentSoilData,
    DepthIntervalPreset,
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


def add_soil_data_to_site(site, preset=DepthIntervalPreset.NRCS):
    ProjectSoilSettings.objects.create(project=site.project, depth_interval_preset=preset)
    if not getattr(site, "soil_data", None):
        SoilData.objects.create(site=site)
    for interval in NRCSIntervalDefaults:
        DepthDependentSoilData.objects.create(
            soil_data=site.soil_data,
            depth_interval_start=interval["depth_interval_start"],
            depth_interval_end=interval["depth_interval_end"],
        )
