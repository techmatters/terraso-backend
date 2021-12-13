# Generated by Django 3.2.9 on 2021-12-12 02:44

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Authorization",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("access_token", models.TextField()),
                ("refresh_token", models.TextField()),
                ("id_token", models.TextField()),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                (
                    "provider",
                    models.CharField(
                        choices=[("apple", "Apple"), ("google", "Google")], max_length=32
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
        ),
    ]
