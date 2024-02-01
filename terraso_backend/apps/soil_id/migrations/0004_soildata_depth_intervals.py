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

# Generated by Django 4.2.5 on 2023-09-21 15:54

from django.db import migrations, models

import apps.soil_id.models.soil_data


class Migration(migrations.Migration):
    dependencies = [
        ("soil_id", "0003_alter_depthdependentsoildata_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="soildata",
            name="depth_intervals",
            field=models.JSONField(
                blank=True,
                default=apps.soil_id.models.soil_data.default_depth_intervals,
                validators=[apps.soil_id.models.soil_data.validate_depth_intervals],
            ),
        ),
    ]
