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

# Generated by Django 4.2.6 on 2023-10-16 21:05

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("soil_id", "0005_projectdepthinterval_projectsoilsettings_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="soildata",
            name="flooding_select",
            field=models.CharField(
                blank=True,
                choices=[
                    ("NONE", "None"),
                    ("RARE", "Rare to occasional"),
                    ("OCCASIONAL", "Occasional"),
                    ("FREQUENT", "Frequent"),
                    ("VERY_FREQUENT", "Very frequent"),
                ],
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="soildata",
            name="grazing",
            field=models.CharField(
                blank=True,
                choices=[
                    ("NOT_GRAZED", "Not Grazed"),
                    ("CATTLE", "Cattle"),
                    ("HORSE", "Horse"),
                    ("GOAT", "Goat"),
                    ("SHEEP", "Sheep"),
                    ("PIG", "Pig"),
                    ("CAMEL", "Camel"),
                    ("WILDLIFE_FOREST", "Wildlife (forest, deer)"),
                    ("WILDLIFE_GRASSLANDS", "Wildlife (grasslands, giraffes, ibex)"),
                ],
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="soildata",
            name="land_cover_select",
            field=models.CharField(
                blank=True,
                choices=[
                    ("FOREST", "Forest"),
                    ("SHRUBLAND", "Shrubland"),
                    ("GRASSLAND", "Grassland"),
                    ("SAVANNA", "Savanna"),
                    ("GARDEN", "Garden"),
                    ("CROPLAND", "Cropland"),
                    ("VILLAGE_OR_CITY", "Village or City"),
                    ("BARREN", "Barren, no vegetation or structures"),
                    ("WATER", "Water"),
                ],
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="soildata",
            name="lime_requirements_select",
            field=models.CharField(
                blank=True,
                choices=[
                    ("LITTLE_OR_NO", "Little or no lime required"),
                    ("SOME", "Some amounts of lime required"),
                    ("HIGH", "High amounts of lime required"),
                    ("VERY_DIFFICULT", "Very difficult to modify with lime"),
                ],
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="soildata",
            name="soil_depth_select",
            field=models.CharField(
                blank=True,
                choices=[
                    ("NOT_FOUND", "Not found"),
                    ("TWENTY_CM_OR_LESS", "20 cm or less"),
                    ("GREATER_THAN_20_LESS_THAN_50_CM", "Greater than 20 and less than 50 cm"),
                    ("BETWEEN_50_AND_70_CM", "Between 50 and 70 cm"),
                    ("GREATER_THAN_70_LESS_THAN_100_CM", "Greater than 70 and less than 100 cm"),
                    ("HUNDRED_CM_OR_GREATER", "100 cm or greater"),
                ],
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="soildata",
            name="surface_cracks_select",
            field=models.CharField(
                blank=True,
                choices=[
                    ("NO_CRACKING", "No cracking"),
                    ("SURFACE_CRACKING_ONLY", "Surface cracking only"),
                    ("DEEP_VERTICAL_CRACKS", "Deep vertical cracks"),
                ],
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="soildata",
            name="surface_salt_select",
            field=models.CharField(
                blank=True,
                choices=[
                    ("NO_SALT", "No salt"),
                    ("SMALL_TEMPORARY_PATCHES", "Small, temporary patches"),
                    ("MOST_OF_SURFACE", "Yes, most of surface"),
                ],
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="soildata",
            name="surface_stoniness_select",
            field=models.CharField(
                blank=True,
                choices=[
                    ("LESS_THAN_01", "< 0.1%"),
                    ("BETWEEN_01_AND_3", "0.1 to 3%"),
                    ("BETWEEN_3_AND_15", "3 to 15%"),
                    ("BETWEEN_15_AND_50", "15 to 50%"),
                    ("BETWEEN_50_AND_90", "50 - 90%"),
                    ("GREATER_THAN_90", "> 90%"),
                ],
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="soildata",
            name="water_table_depth_select",
            field=models.CharField(
                blank=True,
                choices=[
                    ("NOT_FOUND", "Not found"),
                    ("LESS_THAN_30_CM", "<30 cm"),
                    ("BETWEEN_30_AND_45_CM", "30 to 45 cm"),
                    ("BETWEEN_45_AND_75_CM", "45 to 75 cm"),
                    ("BETWEEN_75_AND_120_CM", "75 to 120 cm"),
                    ("GREATER_THAN_120_CM", "> 120 cm"),
                ],
                null=True,
            ),
        ),
    ]
