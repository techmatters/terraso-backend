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
        migrations.AlterField(
            model_name="group",
            name="deleted_at",
            field=models.DateTimeField(db_index=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="groupassociation",
            name="deleted_at",
            field=models.DateTimeField(db_index=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="landscape",
            name="deleted_at",
            field=models.DateTimeField(db_index=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="landscapegroup",
            name="deleted_at",
            field=models.DateTimeField(db_index=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="membership",
            name="deleted_at",
            field=models.DateTimeField(db_index=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="taxonomyterm",
            name="type",
            field=models.CharField(
                choices=[
                    ("ecosystem-type", "Ecosystem Type"),
                    ("language", "Language"),
                    ("livelihood", "Livelihood"),
                    ("commodity", "Commodity"),
                    ("organization", "Organization"),
                    ("agricultural-production-method", "Agricultural Production Method"),
                ],
                max_length=128,
            ),
        ),
        migrations.AlterField(
            model_name="taxonomyterm",
            name="value_original",
            field=models.CharField(
                max_length=128, validators=[apps.core.models.commons.validate_name]
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="deleted_at",
            field=models.DateTimeField(db_index=True, editable=False, null=True),
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
