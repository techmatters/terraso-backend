# Copyright © 2024 Technology Matters
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

# Generated by Django 5.0.6 on 2024-07-10 17:42 (plus manual modifications)

from django.db import migrations, models


def updateDepthIntervalPresets(apps, schema_editor):
    SoilData = apps.get_model("soil_id", "SoilData")
    ProjectSoilSettings = apps.get_model("soil_id", "ProjectSoilSettings")

    for siteSoilData in SoilData.objects.all():
        if siteSoilData.depth_interval_preset == "LANDPKS":
            siteSoilData.depth_interval_preset = "CUSTOM"
            siteSoilData.save(update_fields=["depth_interval_preset"])

    for project in ProjectSoilSettings.objects.all():
        if project.depth_interval_preset == "LANDPKS":
            project.depth_interval_preset = "CUSTOM"
            project.save(update_fields=["depth_interval_preset"])


class Migration(migrations.Migration):

    dependencies = [
        ("soil_id", "0014_soilidcache_soilidcache_coordinate_index"),
    ]

    operations = [
        migrations.AlterField(
            model_name="projectsoilsettings",
            name="depth_interval_preset",
            field=models.CharField(
                choices=[("NRCS", "Nrcs"), ("BLM", "Blm"), ("NONE", "None"), ("CUSTOM", "Custom")],
                default="NRCS",
            ),
        ),
        migrations.AlterField(
            model_name="soildata",
            name="depth_interval_preset",
            field=models.CharField(
                choices=[("BLM", "Blm"), ("NRCS", "Nrcs"), ("CUSTOM", "Custom")], default="NRCS"
            ),
        ),
        migrations.RunPython(updateDepthIntervalPresets),
    ]
