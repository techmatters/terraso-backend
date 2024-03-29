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

# Generated by Django 5.0.2 on 2024-03-07 22:36

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("soil_id", "0011_alter_soildata_depth_interval_preset_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="depthdependentsoildata",
            name="color_hue_substep",
        ),
        migrations.RemoveField(
            model_name="depthdependentsoildata",
            name="color_hue",
        ),
        migrations.RemoveField(
            model_name="depthdependentsoildata",
            name="color_value",
        ),
        migrations.RemoveField(
            model_name="depthdependentsoildata",
            name="color_chroma",
        ),
        migrations.AddField(
            model_name="depthdependentsoildata",
            name="color_photo_used",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="depthdependentsoildata",
            name="color_chroma",
            field=models.FloatField(
                blank=True,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(50),
                ],
            ),
        ),
        migrations.AddField(
            model_name="depthdependentsoildata",
            name="color_hue",
            field=models.FloatField(
                blank=True,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(100),
                ],
            ),
        ),
        migrations.AddField(
            model_name="depthdependentsoildata",
            name="color_value",
            field=models.FloatField(
                blank=True,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(10),
                ],
            ),
        ),
    ]
