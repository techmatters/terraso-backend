# Generated by Django 4.1 on 2022-11-21 21:46

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shared_data", "0007_dataentry_entry_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dataentry",
            name="resource_type",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AlterField(
            model_name="dataentry",
            name="size",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="visualizationconfig",
            name="data_entry",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="visualizations",
                to="shared_data.dataentry",
            ),
        ),
    ]
