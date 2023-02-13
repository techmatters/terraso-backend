# Generated by Django 4.1.6 on 2023-02-13 20:05

from django.db import migrations, models

import apps.core.models.commons


class Migration(migrations.Migration):
    dependencies = [
        ("story_map", "0002_storymap_published_at"),
    ]

    operations = [
        migrations.AlterField(
            model_name="storymap",
            name="title",
            field=models.CharField(
                default=None, max_length=128, validators=[apps.core.models.commons.validate_name]
            ),
        ),
    ]
