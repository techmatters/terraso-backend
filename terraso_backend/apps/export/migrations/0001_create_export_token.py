# Copyright © 2021-2025 Technology Matters
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

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ExportToken",
            fields=[
                (
                    "token",
                    models.CharField(max_length=36, primary_key=True, serialize=False),
                ),
                (
                    "resource_type",
                    models.CharField(
                        choices=[("USER", "User"), ("PROJECT", "Project"), ("SITE", "Site")],
                        max_length=10,
                    ),
                ),
                ("resource_id", models.CharField(max_length=255)),
                ("user_id", models.CharField(max_length=255)),
            ],
            options={
                "db_table": "export_token",
                "indexes": [
                    models.Index(
                        fields=["resource_type", "resource_id"],
                        name="export_toke_resourc_391f43_idx",
                    ),
                    models.Index(
                        fields=["user_id", "resource_type", "resource_id"],
                        name="export_token_user_resource_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=["user_id", "resource_type", "resource_id"],
                        name="unique_user_resource_token",
                    ),
                ],
            },
        ),
    ]
