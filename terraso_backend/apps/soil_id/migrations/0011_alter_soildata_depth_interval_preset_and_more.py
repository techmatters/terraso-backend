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


# Generated by Django 5.0.2 on 2024-03-05 23:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("soil_id", "0010_depthdependentsoildata_color_photo_lighting_condition_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="soildata",
            name="depth_interval_preset",
            field=models.CharField(
                choices=[("LANDPKS", "Landpks"), ("NRCS", "Nrcs"), ("CUSTOM", "Custom")],
                default="LANDPKS",
            ),
        ),
        migrations.AlterField(
            model_name="soildatadepthinterval",
            name="carbonates_enabled",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="soildatadepthinterval",
            name="electrical_conductivity_enabled",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="soildatadepthinterval",
            name="ph_enabled",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="soildatadepthinterval",
            name="sodium_adsorption_ratio_enabled",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="soildatadepthinterval",
            name="soil_color_enabled",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="soildatadepthinterval",
            name="soil_organic_carbon_matter_enabled",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="soildatadepthinterval",
            name="soil_structure_enabled",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="soildatadepthinterval",
            name="soil_texture_enabled",
            field=models.BooleanField(blank=True, null=True),
        ),
    ]
