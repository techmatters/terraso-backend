# Generated by Django 4.0.1 on 2022-02-02 14:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_auto_20220120_2038"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="group",
            options={"get_latest_by": "-created_at", "ordering": ["created_at"]},
        ),
        migrations.RemoveConstraint(
            model_name="landscape",
            name="unique_active_slug",
        ),
        migrations.AddConstraint(
            model_name="group",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("slug",),
                name="core_group_unique_active_slug",
            ),
        ),
        migrations.AddConstraint(
            model_name="landscape",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("slug",),
                name="core_landscape_unique_active_slug",
            ),
        ),
    ]
