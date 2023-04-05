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

# Generated by Django 4.1 on 2022-10-21 20:39

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0019_alter_landscape_population_development_strategy"),
    ]

    operations = [
        migrations.AddField(
            model_name="landscapegroup",
            name="partnership_year",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
