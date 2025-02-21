# Copyright © 2025 Technology Matters
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

# Generated by Django 5.1.2 on 2024-11-07 15:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("story_map", "0005_storymap_membership_list"),
    ]

    operations = [
        migrations.AddField(
            model_name="storymap",
            name="published_configuration",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.RunSQL(
            sql="UPDATE story_map_storymap SET published_configuration = configuration WHERE is_published = True;"
        ),
    ]
