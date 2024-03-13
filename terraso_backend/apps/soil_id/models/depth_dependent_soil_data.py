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

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models.commons import BaseModel
from apps.soil_id.models.depth_interval import BaseDepthInterval
from apps.soil_id.models.soil_data import SoilData


class DepthDependentSoilData(BaseModel, BaseDepthInterval):
    soil_data = models.ForeignKey(
        SoilData, on_delete=models.CASCADE, related_name="depth_dependent_data"
    )

    class Meta(BaseModel.Meta):
        ordering = ["depth_interval_start"]
        constraints = BaseDepthInterval.constraints("soil_data")

    class Texture(models.TextChoices):
        SAND = "SAND"
        LOAMY_SAND = "LOAMY_SAND"
        SANDY_LOAM = "SANDY_LOAM"
        SILT_LOAM = "SILT_LOAM"
        SILT = "SILT"
        LOAM = "LOAM"
        SANDY_CLAY_LOAM = "SANDY_CLAY_LOAM"
        SILTY_CLAY_LOAM = "SILTY_CLAY_LOAM"
        CLAY_LOAM = "CLAY_LOAM"
        SANDY_CLAY = "SANDY_CLAY"
        SILTY_CLAY = "SILTY_CLAY"
        CLAY = "CLAY"

    texture = models.CharField(blank=True, null=True, choices=Texture.choices)

    clay_percent = models.IntegerField(
        blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    class RockFragmentVolume(models.TextChoices):
        VOLUME_0_1 = "VOLUME_0_1", "0 — 1%"
        VOLUME_1_15 = "VOLUME_1_15", "1 — 15%"
        VOLUME_15_35 = "VOLUME_15_35", "15 — 35%"
        VOLUME_35_60 = "VOLUME_35_60", "35 — 60%"
        VOLUME_60 = "VOLUME_60", "> 60%"

    rock_fragment_volume = models.CharField(
        blank=True, null=True, choices=RockFragmentVolume.choices
    )

    color_hue = models.FloatField(
        blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    color_value = models.FloatField(
        blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(10)]
    )

    color_chroma = models.FloatField(
        blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(50)]
    )

    color_photo_used = models.BooleanField(blank=True, null=True)

    class ColorPhotoSoilCondition(models.TextChoices):
        MOIST = "MOIST"
        DRY = "DRY"

    color_photo_soil_condition = models.CharField(
        blank=True, null=True, choices=ColorPhotoSoilCondition
    )

    class ColorPhotoLightingCondition(models.TextChoices):
        EVEN = "EVEN"
        UNEVEN = "UNEVEN"

    color_photo_lighting_condition = models.CharField(
        blank=True, null=True, choices=ColorPhotoLightingCondition
    )

    conductivity = models.DecimalField(
        blank=True, null=True, max_digits=100, decimal_places=2, validators=[MinValueValidator(0)]
    )

    class ConductivityTest(models.TextChoices):
        SATURATED_PASTE = "SATURATED_PASTE"
        SOIL_WATER_1_1 = "SOIL_WATER_1_1", "1:1 soil/water"
        SOIL_WATER_1_2 = "SOIL_WATER_1_2", "1:2 soil/water"
        SOIL_CONTACT_PROBE = "SOIL_CONTACT_PROBE"
        OTHER = "OTHER"

    conductivity_test = models.CharField(blank=True, null=True, choices=ConductivityTest.choices)

    class ConductivityUnit(models.TextChoices):
        MILLISIEMENS_CENTIMETER = "MILLISIEMENS_CENTIMETER", "mS/cm"
        MILLIMHOS_CENTIMETER = "MILLIMHOS_CENTIMETER", "mmhos/cm"
        MICROSIEMENS_METER = "MICROSIEMENS_METER", "µS/m"
        MILLISIEMENS_METER = "MILLISIEMENS_METER", "mS/m"
        DECISIEMENS_METER = "DECISIEMENS_METER", "dS/m"
        OTHER = "OTHER"

    conductivity_unit = models.CharField(blank=True, null=True, choices=ConductivityUnit.choices)

    class SoilStructure(models.TextChoices):
        GRANULAR = "GRANULAR"
        SUBANGULAR_BLOCKY = "SUBANGULAR_BLOCKY"
        ANGULAR_BLOCKY = "ANGULAR_BLOCKY"
        LENTICULAR = "LENTICULAR"
        PLAY = "PLAY"
        WEDGE = "WEDGE"
        PRISMATIC = "PRISMATIC"
        COLUMNAR = "COLUMNAR"
        SINGLE_GRAIN = "SINGLE_GRAIN"
        MASSIVE = "MASSIVE"

    structure = models.CharField(blank=True, null=True, choices=SoilStructure.choices)

    ph = models.DecimalField(
        blank=True,
        null=True,
        max_digits=3,
        decimal_places=1,
        validators=[MinValueValidator(0.0), MaxValueValidator(14.0)],
    )

    class PhTestingSolution(models.TextChoices):
        SOIL_WATER_1_1 = "SOIL_WATER_1_1", "1:1 soil/water"
        SOIL_WATER_1_2 = "SOIL_WATER_1_2", "1:2 soil/water"
        SOIL_WATER_1_2_5 = "SOIL_WATER_1_2_5", "1:2.5 soil/water"
        SOIL_WATER_1_5 = "SOIL_WATER_1_5", "1:5 soil/water"
        SOIL_CACL2_1_1 = "SOIL_CACL2_1_1", "1:1 soil/0.1 M CaCL2"
        SOIL_CACL2_1_2 = "SOIL_CACL2_1_2", "1:2 soil/0.1 M CaCL2"
        SOIL_CACL2_1_5 = "SOIL_CACL2_1_5", "1:5 soil/0.1 M CaCL2"
        SOIL_KCL_1_1 = "SOIL_KCL_1_1", "1:1 soil/1.0 M KCL"
        SOIL_KCL_1_2_5 = "SOIL_KCL_1_2_5", "1:2.5 soil/1.0 M KCL"
        SOIL_KCL_1_5 = "SOIL_KCL_1_5", "1:5 soil/1.0 M KCL"
        SATURATED_PASTE_EXTRACT = "SATURATED_PASTE_EXTRACT"
        OTHER = "OTHER"

    ph_testing_solution = models.CharField(blank=True, null=True, choices=PhTestingSolution.choices)

    class PhTestingMethod(models.TextChoices):
        INDICATOR_STRIP = "INDICATOR_STRIP", "pH indicator strip"
        INDICATOR_SOLUTION = "INDICATOR_SOLUTION", "pH indicator solution"
        METER = "METER", "pH meter"
        OTHER = "OTHER"

    ph_testing_method = models.CharField(blank=True, null=True, choices=PhTestingMethod.choices)

    soil_organic_carbon = models.DecimalField(
        blank=True,
        null=True,
        max_digits=4,
        decimal_places=1,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    soil_organic_matter = models.DecimalField(
        blank=True,
        null=True,
        max_digits=4,
        decimal_places=1,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    class SoilTestingMethod(models.TextChoices):
        DRY_COMBUSTION = "DRY_COMBUSTION"
        WET_OXIDATION = "WET_OXIDATION", "Wet oxidation (Walkey—Black)"
        LOSS_ON_IGNITION = "LOSS_ON_IGNITION", "Loss—on—ignition"
        REFLECTANCE_SPECTROSCOPY = "REFLECTANCE_SPECTROSCOPY"
        FIELD_REFLECTOMETER = "FIELD_REFLECTOMETER"
        OTHER = "OTHER"

    soil_organic_carbon_testing = models.CharField(
        blank=True, null=True, choices=SoilTestingMethod.choices
    )
    soil_organic_matter_testing = models.CharField(
        blank=True, null=True, choices=SoilTestingMethod.choices
    )

    sodium_absorption_ratio = models.DecimalField(
        blank=True, null=True, max_digits=100, decimal_places=1, validators=[MinValueValidator(0)]
    )

    class CarbonateResponse(models.TextChoices):
        NONEFFERVESCENT = "NONEFFERVESCENT", "noneffervescent — No bubbles form"
        VERY_SLIGHTLY_EFFERVESCENT = (
            "VERY_SLIGHTLY_EFFERVESCENT",
            "very slightly effervescent — Few bubbles form",
        )
        SLIGHTLY_EFFERVESCENT = (
            "SLIGHTLY_EFFERVESCENT",
            "slightly effervescent — Numerous bubbles form",
        )
        STRONGLY_EFFERVESCENT = (
            "STRONGLY_EFFERVESCENT",
            "strongly effervescent — Bubbles form a low foam",
        )
        VIOLENTLY_EFFERVESCENT = (
            "VIOLENTLY_EFFERVESCENT",
            "violently effervescent — Bubbles rapidly form a thick foam",
        )

    carbonates = models.CharField(blank=True, null=True, choices=CarbonateResponse.choices)

    @classmethod
    def delete_in_project(cls, project_id):
        return cls.objects.filter(soil_data__site__project__id=project_id).delete()
