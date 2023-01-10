# Generated by Django 4.1.3 on 2023-01-09 18:54

from django.db import migrations, models

import apps.core.models.commons


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0035_landscapedevelopmentstrategy_opportunities"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="group",
            name="core_group_unique_active_slug",
        ),
        migrations.RemoveConstraint(
            model_name="group",
            name="core_group_name_key",
        ),
        migrations.RemoveConstraint(
            model_name="landscape",
            name="core_landscape_unique_active_slug",
        ),
        migrations.RemoveConstraint(
            model_name="landscape",
            name="core_landscape_name_key",
        ),
        migrations.AddConstraint(
            model_name="group",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("slug",),
                name="core_group_unique_active_slug",
                violation_error_message="slug",
            ),
        ),
        migrations.AddConstraint(
            model_name="group",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("name",),
                name="core_group_unique_active_name",
                violation_error_message="name",
            ),
        ),
        migrations.AddConstraint(
            model_name="landscape",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("slug",),
                name="core_landscape_unique_active_slug",
                violation_error_message="slug",
            ),
        ),
        migrations.AddConstraint(
            model_name="landscape",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("name",),
                name="core_landscape_unique_active_name",
                violation_error_message="name",
            ),
        ),
    ]
