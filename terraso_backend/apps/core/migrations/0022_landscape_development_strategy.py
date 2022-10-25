# Generated by Django 4.1 on 2022-10-25 21:23

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0021_landscape_partnership_status"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="landscape",
            name="development_strategy",
        ),
        migrations.AddField(
            model_name="landscapedevelopmentstrategy",
            name="landscape",
            field=models.ForeignKey(
                default="",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="associated_development_strategy",
                to="core.landscape",
            ),
            preserve_default=False,
        ),
    ]
