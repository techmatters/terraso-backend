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
from apps.project_management.models import Project
from apps.soil_id.models.depth_interval import BaseDepthInterval
from apps.soil_id.models.soil_data import SoilDataDepthInterval


class DepthIntervalPreset(models.TextChoices):
    NRCS = "NRCS"
    BLM = "BLM"
    NONE = "NONE"
    CUSTOM = "CUSTOM"


NRCSIntervalDefaults = [
    dict(depth_interval_start=0, depth_interval_end=5),
    dict(depth_interval_start=5, depth_interval_end=15),
    dict(depth_interval_start=15, depth_interval_end=30),
    dict(depth_interval_start=30, depth_interval_end=60),
    dict(depth_interval_start=60, depth_interval_end=100),
    dict(depth_interval_start=100, depth_interval_end=200),
]

BLMIntervalDefaults = [
    dict(depth_interval_start=0, depth_interval_end=1),
    dict(depth_interval_start=1, depth_interval_end=10),
    dict(depth_interval_start=10, depth_interval_end=20),
    dict(depth_interval_start=20, depth_interval_end=50),
    dict(depth_interval_start=50, depth_interval_end=70),
]


class ProjectSoilSettings(BaseModel):
    class Meta(BaseModel.Meta):
        abstract = False
        verbose_name_plural = "project soil settings"

    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name="soil_settings")

    depth_interval_preset = models.CharField(
        default=DepthIntervalPreset.NRCS.value,
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

    @property
    def is_custom_preset(self):
        return self.depth_interval_preset == DepthIntervalPreset.CUSTOM

    @property
    def methods(self):
        field_names = [
            field.name.removesuffix("_enabled")
            for field in SoilDataDepthInterval._meta.fields
            if field.name.endswith("_enabled")
        ]
        return {
            f"{field_name}_enabled": getattr(self, f"{field_name}_required")
            for field_name in field_names
        }


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
