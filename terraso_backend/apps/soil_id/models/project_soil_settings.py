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

from dirtyfields import DirtyFieldsMixin
from django.db import models, transaction

from apps.core.models.commons import BaseModel
from apps.project_management.models.projects import Project
from apps.soil_id.models.depth_dependent_soil_data import DepthDependentSoilData
from apps.soil_id.models.depth_interval import BaseDepthInterval


class DepthIntervalPreset(models.TextChoices):
    LANDPKS = "LANDPKS"
    NRCS = "NRCS"
    NONE = "NONE"
    CUSTOM = "CUSTOM"


LandPKSIntervalDefaults = [
    dict(depth_interval_start=0, depth_interval_end=10),
    dict(depth_interval_start=10, depth_interval_end=20),
    dict(depth_interval_start=20, depth_interval_end=50),
    dict(depth_interval_start=50, depth_interval_end=70),
    dict(depth_interval_start=70, depth_interval_end=100),
    dict(depth_interval_start=100, depth_interval_end=200),
]

NRCSIntervalDefaults = [
    dict(depth_interval_start=0, depth_interval_end=5),
    dict(depth_interval_start=5, depth_interval_end=15),
    dict(depth_interval_start=15, depth_interval_end=30),
    dict(depth_interval_start=30, depth_interval_end=60),
    dict(depth_interval_start=60, depth_interval_end=100),
    dict(depth_interval_start=100, depth_interval_end=200),
]


class ProjectSoilSettings(BaseModel, DirtyFieldsMixin):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name="soil_settings")

    class MeasurementUnit(models.TextChoices):
        IMPERIAL = "IMPERIAL"
        METRIC = "METRIC"

    measurement_units = models.CharField(blank=True, null=True, choices=MeasurementUnit.choices)

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

    def save(self, *args, **kwargs):
        dirty_fields = self.get_dirty_fields()
        with transaction.atomic():
            result = super().save(*args, **kwargs)
            if "depth_interval_preset" in dirty_fields or not self.id:
                # delete project intervals...
                ProjectDepthInterval.objects.filter(project=self).delete()
                # delete related soil data
                DepthDependentSoilData.delete_in_project(self.id)
                # create new intervals
                self.apply_preset()
        return result

    def apply_preset(self):
        match self.depth_interval_preset:
            case DepthIntervalPreset.LANDPKS.value:
                self.make_intervals(LandPKSIntervalDefaults)
            case DepthIntervalPreset.NRCS.value:
                self.make_intervals(NRCSIntervalDefaults)

    def make_intervals(self, presets):
        intervals = [ProjectDepthInterval(project=self, **kwargs) for kwargs in presets]
        return ProjectDepthInterval.objects.bulk_create(intervals)


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
