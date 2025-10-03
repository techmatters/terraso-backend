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

from django.db import migrations, models


def populate_user_ratings_from_selected_soil_id(apps, schema_editor):
    """
    Populates user_ratings from existing selected_soil_id values.
    If selected_soil_id is set, it becomes a SELECTED rating in user_ratings.
    If selected_soil_id is None or empty, user_ratings remains empty.
    """
    SoilMetadata = apps.get_model("soil_id", "SoilMetadata")

    for soil_metadata in SoilMetadata.objects.all():
        if soil_metadata.selected_soil_id:
            # Populate user_ratings with the selected soil ID
            soil_metadata.user_ratings = {
                soil_metadata.selected_soil_id: "SELECTED"
            }
            soil_metadata.save(update_fields=["user_ratings"])


def reverse_populate_selected_soil_id_from_user_ratings(apps, schema_editor):
    """
    Reverse migration: populates selected_soil_id from user_ratings.
    Finds the soil_match_id with SELECTED rating and sets it as selected_soil_id.
    """
    SoilMetadata = apps.get_model("soil_id", "SoilMetadata")

    for soil_metadata in SoilMetadata.objects.all():
        selected_id = None
        for soil_match_id, rating in soil_metadata.user_ratings.items():
            if rating == "SELECTED":
                selected_id = soil_match_id
                break

        soil_metadata.selected_soil_id = selected_id
        soil_metadata.save(update_fields=["selected_soil_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("soil_id", "0022_soilidcache_data_region"),
    ]

    operations = [
        migrations.AddField(
            model_name="soilmetadata",
            name="user_ratings",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(
            populate_user_ratings_from_selected_soil_id,
            reverse_code=reverse_populate_selected_soil_id_from_user_ratings,
        ),
        migrations.RemoveField(
            model_name="soilmetadata",
            name="selected_soil_id",
        ),
    ]
