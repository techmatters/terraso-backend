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
from django.utils.translation import gettext_lazy as _

from apps.core.models.commons import BaseModel
from apps.soil_id.models.soil_data import SoilData

OTHER = "other"


class DepthDependentSoilData(BaseModel):
    soil_data_input = models.ForeignKey(SoilData, on_delete=models.CASCADE)
    depth_top = models.IntegerField(blank=True)
    depth_bottom = models.IntegerField(blank=True)

    SAND = "sand"
    LOAMY_SAND = "loamy sand"
    SANDY_LOAM = "sandy loam"
    SILT_LOAM = "silt loam"
    SILT = "silt"
    LOAM = "loam"
    SANDY_CLAY_LOAM = "sandy clay loam"
    SILTY_CLAY_LOAM = "silty clay loam"
    CLAY_LOAM = "clay loam"
    SANDY_CLAY = "sandy clay"
    SILTY_CLAY = "silty clay"
    CLAY = "clay"

    TEXTURES = (
        (SAND, _("Sand")),
        (LOAMY_SAND, _("Loamy sand")),
        (SANDY_LOAM, _("Sandy loam")),
        (SILT_LOAM, _("Silt loam")),
        (SILT, _("Silt")),
        (LOAM, _("Loam")),
        (SANDY_CLAY_LOAM, _("Sandy clay loam")),
        (SILTY_CLAY_LOAM, _("Silty clay loam")),
        (CLAY_LOAM, _("Clay loam")),
        (SANDY_CLAY, _("Sandy clay")),
        (SILTY_CLAY, _("Silty clay")),
        (CLAY, _("Clay")),
    )
    texture = models.CharField(null=True, choices=TEXTURES)

    ROCK_FRAGMENT_0_1 = "0 — 1%"
    ROCK_FRAGMENT_1_15 = "1 — 15%"
    ROCK_FRAGMENT_15_35 = "15 — 35%"
    ROCK_FRAGMENT_35_60 = "35 — 60%"
    ROCK_FRAGMENT_60 = "> 60%"

    ROCK_FRAGMENT_VOLUMES = (
        (ROCK_FRAGMENT_0_1, _("0 — 1%")),
        (ROCK_FRAGMENT_1_15, _("1 — 15%")),
        (ROCK_FRAGMENT_15_35, _("15 — 35%")),
        (ROCK_FRAGMENT_35_60, _("35 — 60%")),
        (ROCK_FRAGMENT_60, _("> 60%")),
    )
    rock_fragment_volume = models.CharField(null=True, choices=ROCK_FRAGMENT_VOLUMES)

    SUBSTEP_2_5 = "2.5"
    SUBSTEP_5 = "5"
    SUBSTEP_7_5 = "7.5"
    SUBSTEP_10 = "10"

    COLOR_HUES_SUBSTEPS = (
        (SUBSTEP_2_5, _("2.5")),
        (SUBSTEP_2_5, _("5")),
        (SUBSTEP_7_5, _("7.5")),
        (SUBSTEP_10, _("10")),
    )
    color_hue_substeps = models.CharField(null=True, choices=COLOR_HUES_SUBSTEPS)

    RED = "R"
    YELLOW_RED = "YR"
    YELLOW = "Y"
    GREEN_YELLOW = "GY"
    GREEN = "G"
    BLUE = "B"
    BLUE_GREEN = "BG"

    COLOR_HUES = (
        (RED, _("r")),
        (YELLOW_RED, _("yr")),
        (YELLOW, _("y")),
        (GREEN_YELLOW, _("gy")),
        (GREEN, _("g")),
        (BLUE, _("b")),
        (BLUE_GREEN, _("bg")),
    )
    color_hue = models.CharField(null=True, choices=COLOR_HUES)

    COLOR_VALUE_2_5 = "2.5"
    COLOR_VALUE_3 = "3"
    COLOR_VALUE_4 = "4"
    COLOR_VALUE_5 = "5"
    COLOR_VALUE_6 = "6"
    COLOR_VALUE_7 = "7"
    COLOR_VALUE_8 = "8"
    COLOR_VALUE_8_5 = "8.5"
    COLOR_VALUE_9 = "9"
    COLOR_VALUE_9_5 = "9.5"

    COLOR_VALUES = (
        (COLOR_VALUE_2_5, _("2.5")),
        (COLOR_VALUE_3, _("3")),
        (COLOR_VALUE_4, _("4")),
        (COLOR_VALUE_5, _("5")),
        (COLOR_VALUE_6, _("6")),
        (COLOR_VALUE_7, _("7")),
        (COLOR_VALUE_8, _("8")),
        (COLOR_VALUE_8_5, _("8.5")),
        (COLOR_VALUE_9, _("9")),
        (COLOR_VALUE_9_5, _("9.5")),
    )
    color_value = models.CharField(null=True, choices=COLOR_VALUES)

    COLOR_CHROMA_1 = "1"
    COLOR_CHROMA_2 = "2"
    COLOR_CHROMA_3 = "3"
    COLOR_CHROMA_4 = "4"
    COLOR_CHROMA_5 = "5"
    COLOR_CHROMA_6 = "6"
    COLOR_CHROMA_7 = "7"
    COLOR_CHROMA_8 = "8"

    COLOR_CHROMAS = (
        (COLOR_CHROMA_1, _("1")),
        (COLOR_CHROMA_2, _("2")),
        (COLOR_CHROMA_3, _("3")),
        (COLOR_CHROMA_4, _("4")),
        (COLOR_CHROMA_5, _("5")),
        (COLOR_CHROMA_6, _("6")),
        (COLOR_CHROMA_7, _("7")),
        (COLOR_CHROMA_8, _("8")),
    )
    color_chroma = models.CharField(null=True, choices=COLOR_CHROMAS)

    conductivity = models.DecimalField(
        null=True, max_digits=100, decimal_places=2, validators=[MinValueValidator(0)]
    )

    CONDUCTIVITY_SATURATED_PASTE = "saturated paste"
    CONDUCTIVITY_SOIL_WATER_1_1 = "1:1 soil/water"
    CONDUCTIVITY_SOIL_WATER_1_2 = "1:2 soil/water"
    CONDUCTIVITY_SOIL_CONTACT_PROBE = "soil contact probe"

    CONDUCTIVITY_TESTS = (
        (CONDUCTIVITY_SATURATED_PASTE, _("Saturated paste")),
        (CONDUCTIVITY_SOIL_WATER_1_1, _("1:1 soil/water")),
        (CONDUCTIVITY_SOIL_WATER_1_2, _("1:2 soil/water")),
        (CONDUCTIVITY_SOIL_CONTACT_PROBE, _("Soil contact probe")),
        (OTHER, _("Other")),
    )
    conductivity_test = models.CharField(null=True, choices=CONDUCTIVITY_TESTS)

    MILLISIEMENS_CENTIMETER = "mS/cm"
    MILLIMHOS_CENTIMETER = "mmhos/cm"
    MICROSIEMENS_METER = "µS/m"
    MILLISIEMENS_METER = "mS/m"
    DECISIEMENS_METER = "dS/m"

    CONDUCTIVITY_UNITS = (
        (MILLISIEMENS_CENTIMETER, _("mS/cm")),
        (MILLIMHOS_CENTIMETER, _("mmhos/cm")),
        (MICROSIEMENS_METER, _("µS/m")),
        (MILLISIEMENS_METER, _("mS/m")),
        (DECISIEMENS_METER, _("dS/m")),
        (OTHER, _("other")),
    )
    conductivity_unit = models.CharField(null=True, choices=CONDUCTIVITY_UNITS)

    GRANULAR = "granular"
    SUBANGULAR_BLOCKY = "subangular blocky"
    ANGULAR_BLOCKY = "angular blocky"
    LENTICULAR = "lenticular"
    PLAY = "play"
    WEDGE = "wedge"
    PRISMATIC = "prismatic"
    COLUMNAR = "columnar"
    SINGLE_GRAIN = "single grain"
    MASSIVE = "massive"

    STRUCTURES = (
        (GRANULAR, _("Granular")),
        (SUBANGULAR_BLOCKY, _("Subangular Blocky")),
        (ANGULAR_BLOCKY, _("Angular Blocky")),
        (LENTICULAR, _("lenticular")),
        (PLAY, _("Play")),
        (WEDGE, _("Wedge")),
        (PRISMATIC, _("Prismatic")),
        (COLUMNAR, _("Columnar")),
        (SINGLE_GRAIN, _("Single Grain")),
        (MASSIVE, _("Massive")),
    )
    structure = models.CharField(null=True, choices=STRUCTURES)

    ph = models.DecimalField(
        null=True,
        max_digits=3,
        decimal_places=1,
        validators=[MinValueValidator(0.0), MaxValueValidator(14.0)],
    )

    PH_TESTING_SOIL_WATER_1_1 = "1:1 soil/water"
    PH_TESTING_SOIL_WATER_1_2 = "1:2 soil/water"
    PH_TESTING_SOIL_WATER_1_2_5 = "1:2.5 soil/water"
    PH_TESTING_SOIL_WATER_1_5 = "1:5 soil/water"
    PH_TESTING_SOIL_CACL2_1_1 = "1:1 soil/0.1 M CaCL2"
    PH_TESTING_SOIL_CACL2_1_2 = "1:2 soil/0.1 M CaCL2"
    PH_TESTING_SOIL_CACL2_1_5 = "1:5 soil/0.1 M CaCL2"
    PH_TESTING_SOIL_KCL_1_1 = "1:1 soil/1.0 M KCL"
    PH_TESTING_SOIL_KCL_1_2_5 = "1:2.5 soil/1.0 M KCL"
    PH_TESTING_SOIL_KCL_1_5 = "1:5 soil/1.0 M KCL"
    PH_TESTING_SATURATED_PASTE_EXTRACT = "saturated paste extract"

    PH_TESTING_SOLUTIONS = (
        (PH_TESTING_SOIL_WATER_1_1, _("1:1 soil/water")),
        (PH_TESTING_SOIL_WATER_1_2, _("1:2 soil/water")),
        (PH_TESTING_SOIL_WATER_1_2_5, _("1:2.5 soil/water")),
        (PH_TESTING_SOIL_WATER_1_5, _("1:5 soil/water")),
        (PH_TESTING_SOIL_CACL2_1_1, _("1:1 soil/0.1 M CaCL2")),
        (PH_TESTING_SOIL_CACL2_1_2, _("1:2 soil/0.1 M CaCL2")),
        (PH_TESTING_SOIL_CACL2_1_5, _("1:5 soil/0.1 M CaCL2")),
        (PH_TESTING_SOIL_KCL_1_1, _("1:1 soil/1.0 M KCL")),
        (PH_TESTING_SOIL_KCL_1_2_5, _("1:2.5 soil/1.0 M KCL")),
        (PH_TESTING_SOIL_KCL_1_5, _("1:5 soil/1.0 M KCL")),
        (PH_TESTING_SATURATED_PASTE_EXTRACT, _("Saturated Paste Extract")),
        (OTHER, _("Other")),
    )
    ph_testing_solution = models.CharField(null=True, choices=PH_TESTING_SOLUTIONS)

    PH_TESTING_INDICATOR_STRIP = "pH indicator strip"
    PH_TESTING_INDICATOR_SOLUTION = "pH indicator solution"
    PH_TESTING_METER = "pH meter"

    PH_TESTING_METHODS = (
        (PH_TESTING_INDICATOR_STRIP, _("pH indicator strip")),
        (PH_TESTING_INDICATOR_SOLUTION, _("pH indicator solution")),
        (PH_TESTING_METER, _("pH meter")),
        (OTHER, _("other")),
    )
    ph_testing_method = models.CharField(null=True, choices=PH_TESTING_METHODS)

    soil_organic_carbon = models.DecimalField(
        null=True,
        max_digits=4,
        decimal_places=1,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    soil_organic_matter = models.DecimalField(
        null=True,
        max_digits=4,
        decimal_places=1,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    SOIL_TESTING_DRY_COMBUSTION = "dry combustion"
    SOIL_TESTING_WET_OXIDATION = "wet oxidation (Walkey—Black)"
    SOIL_TESTING_LOSS_ON_IGNITION = "loss—on—ignition"
    SOIL_TESTING_REFLECTANCE_SPECTROSCOPY = "reflectance spectroscopy"
    SOIL_TESTING_FIELD_REFLECTOMETER = "field reflectometer"

    SOIL_TESTING_METHODS = (
        (SOIL_TESTING_DRY_COMBUSTION, _("Dry combustion")),
        (SOIL_TESTING_WET_OXIDATION, _("Wet oxidation (Walkey—Black)")),
        (SOIL_TESTING_LOSS_ON_IGNITION, _("Loss—on—ignition")),
        (SOIL_TESTING_REFLECTANCE_SPECTROSCOPY, _("Reflectance spectroscopy")),
        (SOIL_TESTING_FIELD_REFLECTOMETER, _("Field reflectometer")),
        (OTHER, _("Other")),
    )
    soil_organic_carbon_testing = models.CharField(null=True, choices=SOIL_TESTING_METHODS)
    soil_organic_matter_testing = models.CharField(null=True, choices=SOIL_TESTING_METHODS)

    sodium_absorption_ratio = models.DecimalField(
        null=True, max_digits=100, decimal_places=2, validators=[MinValueValidator(0)]
    )

    bedrock = models.PositiveIntegerField(null=True)

    NONEFFERVESCENT = "noneffervescent — No bubbles form"
    VERY_SLIGHTLY_EFFERVESCENT = "very slightly effervescent — Few bubbles form"
    SLIGHTLY_EFFERVESCENT = "slightly effervescent — Numerous bubbles form"
    STRONGLY_EFFERVESCENT = "strongly effervescent — Bubbles form a low foam"
    VIOLENTLY_EFFERVESCENT = "violently effervescent — Bubbles rapidly form a thick foam"

    CARBONATES = (
        (NONEFFERVESCENT, _("Noneffervescent — No bubbles form")),
        (VERY_SLIGHTLY_EFFERVESCENT, _("Very slightly effervescent — Few bubbles form")),
        (SLIGHTLY_EFFERVESCENT, _("Slightly effervescent — Numerous bubbles form")),
        (STRONGLY_EFFERVESCENT, _("Strongly effervescent — Bubbles form a low foam")),
        (VIOLENTLY_EFFERVESCENT, _("Violently effervescent — Bubbles rapidly form a thick foam")),
    )

    carbonate = models.CharField(null=True, choices=CARBONATES)
