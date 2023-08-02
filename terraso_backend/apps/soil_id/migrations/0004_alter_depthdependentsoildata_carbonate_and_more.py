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

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("soil_id", "0003_depthdependentsoildata_carbonate_and_more"),
    ]

    operations = [
        migrations.AlterField(
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
        migrations.AlterField(
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
        migrations.AlterField(
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
        migrations.AlterField(
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
        migrations.AlterField(
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
    ]
