# Copyright © 2023 Technology Matters
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

from django.db import models

from apps.core.models.commons import BaseModel
from apps.project_management.models.projects import Project
from apps.soil_id.models.depth_interval import BaseDepthInterval


class ProjectSoilSettings(BaseModel):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name="soil_settings")

    class MeasurementUnit(models.TextChoices):
        IMPERIAL = "IMPERIAL"
        METRIC = "METRIC"

    measurement_units = models.CharField(blank=True, null=True, choices=MeasurementUnit.choices)

    class DepthIntervalPreset(models.TextChoices):
        LANDPKS = "LANDPKS"
        NRCS = "NRCS"
        NONE = "NONE"
        CUSTOM = "CUSTOM"

    depth_interval_preset = models.CharField(
        null=False,
        default=DepthIntervalPreset.LANDPKS.value,
        choices=DepthIntervalPreset.choices,
    )

    soil_pit_required = models.BooleanField(blank=True, default=False)
    slope_required = models.BooleanField(blank=True, default=False)
    soil_texture_required = models.BooleanField(blank=True, default=False)
    soil_color_required = models.BooleanField(blank=True, default=False)
    vertical_cracking_required = models.BooleanField(blank=True, default=False)
    carbonates_required = models.BooleanField(blank=True, default=False)
    ph_required = models.BooleanField(blank=True, default=False)
    soil_organic_carbon_matter_required = models.BooleanField(blank=True, default=False)
    electrical_conductivity_required = models.BooleanField(blank=True, default=False)
    sodium_adsorption_ratio_required = models.BooleanField(blank=True, default=False)
    soil_structure_required = models.BooleanField(blank=True, default=False)
    land_use_land_cover_required = models.BooleanField(blank=True, default=False)
    soil_limitations_required = models.BooleanField(blank=True, default=False)
    photos_required = models.BooleanField(blank=True, default=False)
    notes_required = models.BooleanField(blank=True, default=False)


class ProjectDepthInterval(BaseModel, BaseDepthInterval):
    project = models.ForeignKey(
        ProjectSoilSettings, on_delete=models.CASCADE, related_name="depth_intervals"
    )
    label = models.CharField(blank=True, max_length=10)

    class Meta(BaseModel.Meta):
        ordering = ["depth_interval_start"]
        constraints = BaseDepthInterval.constraints("project")

    def clean(self):
        super().clean()
        BaseDepthInterval.validate_intervals(list(self.project.depth_intervals.all()))
