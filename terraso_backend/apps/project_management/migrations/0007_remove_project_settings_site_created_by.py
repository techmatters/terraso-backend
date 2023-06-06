# Generated by Django 4.2.2 on 2023-06-06 07:33

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("project_management", "0006_make_projectsettings_not_null"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="project",
            name="settings",
        ),
        migrations.AddField(
            model_name="site",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="created_by",
                to=settings.AUTH_USER_MODEL,
                verbose_name="user who created the site",
            ),
        ),
    ]
