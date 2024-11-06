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


# Generated by Django 5.1.2 on 2024-11-06 23:19

from django.db import migrations, models

import apps.soil_id.models.soil_data_history


class Migration(migrations.Migration):

    dependencies = [
        ("soil_id", "0019_soildatahistory"),
    ]

    operations = [
        migrations.AlterField(
            model_name="projectsoilsettings",
            name="slope_required",
            field=models.BooleanField(blank=True, default=True),
        ),
        migrations.AlterField(
            model_name="projectsoilsettings",
            name="soil_color_required",
            field=models.BooleanField(blank=True, default=True),
        ),
        migrations.AlterField(
            model_name="projectsoilsettings",
            name="soil_pit_required",
            field=models.BooleanField(blank=True, default=True),
        ),
        migrations.AlterField(
            model_name="projectsoilsettings",
            name="soil_texture_required",
            field=models.BooleanField(blank=True, default=True),
        ),
        migrations.AlterField(
            model_name="soildatahistory",
            name="soil_data_changes",
            field=models.JSONField(encoder=apps.soil_id.models.soil_data_history.JSONEncoder),
        ),
    ]
