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

import random
import string

from django.db import migrations, models


def update_rows(apps, schema_editor):
    StoryMap = apps.get_model("story_map", "StoryMap")
    for obj in StoryMap.objects.all():
        obj.story_map_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=7))
        obj.save()


class Migration(migrations.Migration):
    dependencies = [
        ("story_map", "0003_alter_storymap_title"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="storymap",
            name="story_map_storymap_unique_active_slug",
        ),
        migrations.AddField(
            model_name="storymap",
            name="story_map_id",
            field=models.CharField(
                default="",
                max_length=10,
            ),
        ),
        migrations.RunPython(update_rows),
        migrations.AddConstraint(
            model_name="storymap",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("slug", "story_map_id"),
                name="story_map_storymap_unique_active_slug_story_map_id",
            ),
        ),
    ]
