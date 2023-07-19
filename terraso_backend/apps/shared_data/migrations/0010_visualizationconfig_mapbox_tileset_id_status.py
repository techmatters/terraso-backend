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

# Generated by Django 4.2.2 on 2023-06-26 23:21

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("shared_data", "0009_alter_dataentry_resource_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="visualizationconfig",
            name="mapbox_tileset_id",
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name="visualizationconfig",
            name="mapbox_tileset_status",
            field=models.CharField(
                choices=[("pending", "Pending"), ("ready", "Ready")],
                default="pending",
                max_length=128,
            ),
        ),
    ]
