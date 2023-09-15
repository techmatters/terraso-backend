# Generated by Django 4.2.5 on 2023-09-15 15:27

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("project_management", "0016_auto_20230915_1527"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="project",
            name="group",
        ),
        migrations.AlterField(
            model_name="project",
            name="membership_list",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                to="collaboration.membershiplist",
                null=False,
            ),
        ),
    ]
