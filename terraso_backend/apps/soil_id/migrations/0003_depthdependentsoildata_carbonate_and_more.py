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
        ("soil_id", "0002_depthdependentsoildata_bedrock_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="depthdependentsoildata",
            name="carbonate",
            field=models.CharField(
                choices=[
                    ("noneffervescent - No bubbles form", "Noneffervescent - No bubbles form"),
                    (
                        "very slightly effervescent - Few bubbles form",
                        "Very slightly effervescent - Few bubbles form",
                    ),
                    (
                        "slightly effervescent - Numerous bubbles form",
                        "Slightly effervescent - Numerous bubbles form",
                    ),
                    (
                        "strongly effervescent - Bubbles form a low foam",
                        "Strongly effervescent - Bubbles form a low foam",
                    ),
                    (
                        "violently effervescent - Bubbles rapidly form a thick foam",
                        "Violently effervescent - Bubbles rapidly form a thick foam",
                    ),
                ],
                null=True,
            ),
        ),
        migrations.AlterField(
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
        migrations.AlterField(
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
        migrations.AlterField(
            model_name="depthdependentsoildata",
            name="soil_organic_carbon_testing",
            field=models.CharField(
                choices=[
                    ("dry combustion", "Dry combustion"),
                    ("wet oxidation (Walkey-Black)", "Wet oxidation (Walkey-Black)"),
                    ("loss-on-ignition", "Loss-on-ignition"),
                    ("reflectance spectroscopy", "Reflectance spectroscopy"),
                    ("field reflectometer", "Field reflectometer"),
                    ("other", "Other"),
                ],
                null=True,
            ),
        ),
        migrations.AlterField(
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
        migrations.AlterField(
            model_name="depthdependentsoildata",
            name="soil_organic_matter_testing",
            field=models.CharField(
                choices=[
                    ("dry combustion", "Dry combustion"),
                    ("wet oxidation (Walkey-Black)", "Wet oxidation (Walkey-Black)"),
                    ("loss-on-ignition", "Loss-on-ignition"),
                    ("reflectance spectroscopy", "Reflectance spectroscopy"),
                    ("field reflectometer", "Field reflectometer"),
                    ("other", "Other"),
                ],
                null=True,
            ),
        ),
    ]
