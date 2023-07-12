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

# Generated by Django 4.2 on 2023-05-05 16:46

import uuid

import django.db.models.deletion
import rules.contrib.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "project_management",
            "0009_archive_projects",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="settings",
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="project_management.projectsettings",
            ),
        ),
    ]
