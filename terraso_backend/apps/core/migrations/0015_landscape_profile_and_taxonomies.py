﻿# Copyright © 2021-2023 Technology Matters
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see https://www.gnu.org/licenses/.

# Generated by Django 4.1 on 2022-10-12 19:52

import uuid

import django.db.models.deletion
import rules.contrib.models
from django.conf import settings
from django.db import migrations, models

import apps.core.models.commons


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0014_group_membership_type_membership_membership_status_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="LandscapeDevelopmentStrategy",
            fields=[
                ("deleted_at", models.DateTimeField(db_index=True, editable=False, null=True)),
                ("deleted_by_cascade", models.BooleanField(default=False, editable=False)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("objectives", models.TextField(blank=True, default="")),
                ("problem_situtation", models.TextField(blank=True, default="")),
                ("intervention_strategy", models.TextField(blank=True, default="")),
                ("other_information", models.TextField(blank=True, default="")),
            ],
            options={
                "ordering": ["created_at"],
                "get_latest_by": "-created_at",
                "abstract": False,
            },
            bases=(rules.contrib.models.RulesModelMixin, models.Model),
        ),
        migrations.AddField(
            model_name="landscape",
            name="area_type",
            field=models.CharField(
                blank=True,
                choices=[("rural", "Rural"), ("peri-urban", "Peri-Urban"), ("urban", "Urban")],
                default="",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="landscape",
            name="email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
        migrations.AddField(
            model_name="landscape",
            name="population",
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name="landscapegroup",
            name="is_partnership",
            field=models.BooleanField(blank=True, default=False),
        ),
        migrations.CreateModel(
            name="TaxonomyTerm",
            fields=[
                ("deleted_at", models.DateTimeField(db_index=True, editable=False, null=True)),
                ("deleted_by_cascade", models.BooleanField(default=False, editable=False)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("slug", models.SlugField(blank=True, editable=False, max_length=250)),
                (
                    "name",
                    models.CharField(
                        max_length=128,
                        unique=True,
                        validators=[apps.core.models.commons.validate_name],
                    ),
                ),
                (
                    "type",
                    models.CharField(
                        max_length=128,
                        unique=True,
                        validators=[apps.core.models.commons.validate_name],
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_taxonomy_terms",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["created_at"],
                "get_latest_by": "-created_at",
                "abstract": False,
            },
            bases=(rules.contrib.models.RulesModelMixin, models.Model),
        ),
        migrations.AddField(
            model_name="landscape",
            name="development_strategy",
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="core.landscapedevelopmentstrategy",
            ),
        ),
        migrations.AddField(
            model_name="landscape",
            name="taxonomy_terms",
            field=models.ManyToManyField(to="core.taxonomyterm"),
        ),
        migrations.AddConstraint(
            model_name="taxonomyterm",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("type", "slug"),
                name="core_taxonomyterm_unique_active_slug",
            ),
        ),
    ]
