# Generated by Django 4.2 on 2023-05-02 15:42

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("shared_data", "0009_alter_dataentry_resource_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dataentry",
            name="created_by",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="dataentry",
            name="deleted_at",
            field=models.DateTimeField(db_index=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="visualizationconfig",
            name="deleted_at",
            field=models.DateTimeField(db_index=True, editable=False, null=True),
        ),
    ]
