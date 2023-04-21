# Generated by Django 4.2 on 2023-04-20 21:06

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0040_website_length"),
    ]

    operations = [
        migrations.AddField(
            model_name="group",
            name="privacy_type",
            field=models.CharField(
                choices=[("private", "Private"), ("public", "Public")],
                default="public",
                max_length=64,
            ),
        ),
    ]
