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
    dependencies = [
        ("export", "0001_create_export_token"),
    ]

    operations = [
        # Add user_id field to ExportToken
        migrations.AddField(
            model_name="exporttoken",
            name="user_id",
            field=models.CharField(max_length=255, default=""),
            preserve_default=False,
        ),
        # Add composite index on [user_id, resource_type, resource_id]
        migrations.AddIndex(
            model_name="exporttoken",
            index=models.Index(
                fields=["user_id", "resource_type", "resource_id"],
                name="export_token_user_resource_idx",
            ),
        ),
        # Add unique constraint on [user_id, resource_type, resource_id]
        migrations.AddConstraint(
            model_name="exporttoken",
            constraint=models.UniqueConstraint(
                fields=["user_id", "resource_type", "resource_id"],
                name="unique_user_resource_token",
            ),
        ),
    ]
