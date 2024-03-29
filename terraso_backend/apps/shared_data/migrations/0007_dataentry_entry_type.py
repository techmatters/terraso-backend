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

# Generated by Django 4.1 on 2022-11-15 20:39

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("shared_data", "0006_visualizationconfig_title_group_slug"),
    ]

    operations = [
        migrations.AddField(
            model_name="dataentry",
            name="entry_type",
            field=models.CharField(
                choices=[("file", "File"), ("link", "Link")], default="file", max_length=32
            ),
            preserve_default=False,
        ),
    ]
