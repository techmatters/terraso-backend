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


import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("soil_id", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="depthdependentsoildata",
            name="bedrock",
            field=models.PositiveIntegerField(null=True),
        ),
        migrations.AddField(
            model_name="depthdependentsoildata",
            name="carbonate",
            field=models.CharField(
                choices=[
                    ("noneffervescent — No bubbles form", "Noneffervescent — No bubbles form"),
                    (
                        "very slightly effervescent — Few bubbles form",
                        "Very slightly effervescent — Few bubbles form",
                    ),
                    (
                        "slightly effervescent — Numerous bubbles form",
                        "Slightly effervescent — Numerous bubbles form",
                    ),
                    (
                        "strongly effervescent — Bubbles form a low foam",
                        "Strongly effervescent — Bubbles form a low foam",
                    ),
                    (
                        "violently effervescent — Bubbles rapidly form a thick foam",
                        "Violently effervescent — Bubbles rapidly form a thick foam",
                    ),
                ],
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="depthdependentsoildata",
            name="color_chroma",
            field=models.IntegerField(
                choices=[
                    (1, "1"),
                    (2, "2"),
                    (3, "3"),
                    (4, "4"),
                    (5, "5"),
                    (6, "6"),
                    (7, "7"),
                    (8, "8"),
                ],
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="depthdependentsoildata",
            name="color_hue",
            field=models.CharField(
                choices=[
                    ("R", "r"),
                    ("YR", "yr"),
                    ("Y", "y"),
                    ("GY", "gy"),
                    ("G", "g"),
                    ("B", "b"),
                    ("BG", "bg"),
                ],
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="depthdependentsoildata",
            name="color_hue_substeps",
            field=models.CharField(
                choices=[("2.5", "2.5"), ("2.5", "5"), ("7.5", "7.5"), ("10", "10")], null=True
            ),
        ),
        migrations.AddField(
            model_name="depthdependentsoildata",
            name="color_value",
            field=models.DecimalField(
                choices=[
                    (2.5, "2.5"),
                    (3, "3"),
                    (4, "4"),
                    (5, "5"),
                    (6, "6"),
                    (7, "7"),
                    (8, "8"),
                    (8.5, "8.5"),
                    (9, "9"),
                    (9.5, "9.5"),
                ],
                decimal_places=1,
                max_digits=2,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="depthdependentsoildata",
            name="conductivity",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=100,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        migrations.AddField(
            model_name="depthdependentsoildata",
            name="conductivity_test",
            field=models.CharField(
                choices=[
                    ("saturated paste", "Saturated paste"),
                    ("1:1 soil/water", "1:1 soil/water"),
                    ("1:2 soil/water", "1:2 soil/water"),
                    ("soil contact probe", "Soil contact probe"),
                    ("other", "Other"),
                ],
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="depthdependentsoildata",
            name="conductivity_unit",
            field=models.CharField(
                choices=[
                    ("mS/cm", "mS/cm"),
                    ("mmhos/cm", "mmhos/cm"),
                    ("µS/m", "µS/m"),
                    ("mS/m", "mS/m"),
                    ("dS/m", "dS/m"),
                    ("other", "other"),
                ],
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="depthdependentsoildata",
            name="ph",
            field=models.DecimalField(
                decimal_places=1,
                max_digits=3,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(0.0),
                    django.core.validators.MaxValueValidator(14.0),
                ],
            ),
        ),
        migrations.AddField(
            model_name="depthdependentsoildata",
            name="ph_testing_method",
            field=models.CharField(
                choices=[
                    ("pH indicator strip", "pH indicator strip"),
                    ("pH indicator solution", "pH indicator solution"),
                    ("pH meter", "pH meter"),
                    ("other", "other"),
                ],
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="depthdependentsoildata",
            name="ph_testing_solution",
            field=models.CharField(
                choices=[
                    ("1:1 soil/water", "1:1 soil/water"),
                    ("1:2 soil/water", "1:2 soil/water"),
                    ("1:2.5 soil/water", "1:2.5 soil/water"),
                    ("1:5 soil/water", "1:5 soil/water"),
                    ("1:1 soil/0.1 M CaCL2", "1:1 soil/0.1 M CaCL2"),
                    ("1:2 soil/0.1 M CaCL2", "1:2 soil/0.1 M CaCL2"),
                    ("1:5 soil/0.1 M CaCL2", "1:5 soil/0.1 M CaCL2"),
                    ("1:1 soil/1.0 M KCL", "1:1 soil/1.0 M KCL"),
                    ("1:2.5 soil/1.0 M KCL", "1:2.5 soil/1.0 M KCL"),
                    ("1:5 soil/1.0 M KCL", "1:5 soil/1.0 M KCL"),
                    ("saturated paste extract", "Saturated Paste Extract"),
                    ("other", "Other"),
                ],
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="depthdependentsoildata",
            name="rock_fragment_volume",
            field=models.CharField(
                choices=[
                    ("0 — 1%", "0 — 1%"),
                    ("1 — 15%", "1 — 15%"),
                    ("15 — 35%", "15 — 35%"),
                    ("35 — 60%", "35 — 60%"),
                    ("> 60%", "> 60%"),
                ],
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="depthdependentsoildata",
            name="sodium_absorption_ratio",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=100,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        migrations.AddField(
            model_name="depthdependentsoildata",
            name="soil_organic_carbon",
            field=models.DecimalField(
                decimal_places=1,
                max_digits=4,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(100),
                ],
            ),
        ),
        migrations.AddField(
            model_name="depthdependentsoildata",
            name="soil_organic_carbon_testing",
            field=models.CharField(
                choices=[
                    ("dry combustion", "Dry combustion"),
                    ("wet oxidation (Walkey—Black)", "Wet oxidation (Walkey—Black)"),
                    ("loss—on—ignition", "Loss—on—ignition"),
                    ("reflectance spectroscopy", "Reflectance spectroscopy"),
                    ("field reflectometer", "Field reflectometer"),
                    ("other", "Other"),
                ],
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="depthdependentsoildata",
            name="soil_organic_matter",
            field=models.DecimalField(
                decimal_places=1,
                max_digits=4,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(100),
                ],
            ),
        ),
        migrations.AddField(
            model_name="depthdependentsoildata",
            name="soil_organic_matter_testing",
            field=models.CharField(
                choices=[
                    ("dry combustion", "Dry combustion"),
                    ("wet oxidation (Walkey—Black)", "Wet oxidation (Walkey—Black)"),
                    ("loss—on—ignition", "Loss—on—ignition"),
                    ("reflectance spectroscopy", "Reflectance spectroscopy"),
                    ("field reflectometer", "Field reflectometer"),
                    ("other", "Other"),
                ],
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="depthdependentsoildata",
            name="structure",
            field=models.CharField(
                choices=[
                    ("granular", "Granular"),
                    ("subangular blocky", "Subangular Blocky"),
                    ("angular blocky", "Angular Blocky"),
                    ("lenticular", "lenticular"),
                    ("play", "Play"),
                    ("wedge", "Wedge"),
                    ("prismatic", "Prismatic"),
                    ("columnar", "Columnar"),
                    ("single grain", "Single Grain"),
                    ("massive", "Massive"),
                ],
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="depthdependentsoildata",
            name="texture",
            field=models.CharField(
                choices=[
                    ("sand", "Sand"),
                    ("loamy sand", "Loamy sand"),
                    ("sandy loam", "Sandy loam"),
                    ("silt loam", "Silt loam"),
                    ("silt", "Silt"),
                    ("loam", "Loam"),
                    ("sandy clay loam", "Sandy clay loam"),
                    ("silty clay loam", "Silty clay loam"),
                    ("clay loam", "Clay loam"),
                    ("sandy clay", "Sandy clay"),
                    ("silty clay", "Silty clay"),
                    ("clay", "Clay"),
                ],
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="soildata",
            name="cross_slope",
            field=models.IntegerField(
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(100),
                ],
            ),
        ),
        migrations.AddField(
            model_name="soildata",
            name="down_slope",
            field=models.IntegerField(
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(100),
                ],
            ),
        ),
        migrations.AddField(
            model_name="soildata",
            name="slope_shape",
            field=models.CharField(
                choices=[("concave", "Concave"), ("convex", "Convex"), ("linear", "Linear")],
                null=True,
            ),
        ),
    ]
