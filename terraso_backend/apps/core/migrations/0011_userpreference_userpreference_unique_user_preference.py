# Generated by Django 4.0.2 on 2022-02-15 20:31

import uuid

import django.db.models.deletion
import rules.contrib.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_landscape_area_polygon"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserPreference",
            fields=[
                ("deleted_at", models.DateTimeField(editable=False, null=True)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("key", models.CharField(max_length=128)),
                ("value", models.TextField(blank=True, default="", max_length=512)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="preferences",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            bases=(rules.contrib.models.RulesModelMixin, models.Model),
        ),
        migrations.AddConstraint(
            model_name="userpreference",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("key", "user"),
                name="unique_user_preference",
            ),
        ),
    ]
