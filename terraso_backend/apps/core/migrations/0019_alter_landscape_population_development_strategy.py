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

# Generated by Django 4.1 on 2022-10-20 18:34

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0018_remove_landscape_area_type_landscape_area_types"),
    ]

    operations = [
        migrations.AlterField(
            model_name="landscape",
            name="development_strategy",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="core.landscapedevelopmentstrategy",
            ),
        ),
        migrations.AlterField(
            model_name="landscape",
            name="population",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
