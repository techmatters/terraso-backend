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


import uuid

import django.db.models.deletion
import rules.contrib.models
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("project_management", "0014_alter_project_description"),
    ]

    operations = [
        migrations.CreateModel(
            name="SoilData",
            fields=[
                ("deleted_at", models.DateTimeField(db_index=True, editable=False, null=True)),
                ("deleted_by_cascade", models.BooleanField(default=False, editable=False)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "site",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE, to="project_management.site"
                    ),
                ),
            ],
            options={
                "ordering": ["created_at"],
                "get_latest_by": "-created_at",
                "abstract": False,
            },
            bases=(rules.contrib.models.RulesModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name="DepthDependentSoilData",
            fields=[
                ("deleted_at", models.DateTimeField(db_index=True, editable=False, null=True)),
                ("deleted_by_cascade", models.BooleanField(default=False, editable=False)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("depth_top", models.IntegerField(blank=True)),
                ("depth_bottom", models.IntegerField(blank=True)),
                (
                    "soil_data_input",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="soil_id.soildata"
                    ),
                ),
            ],
            options={
                "ordering": ["created_at"],
                "get_latest_by": "-created_at",
                "abstract": False,
            },
            bases=(rules.contrib.models.RulesModelMixin, models.Model),
        ),
    ]
