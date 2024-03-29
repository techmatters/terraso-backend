# Copyright © 2021-2023 Technology Matters
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

# Generated by Django 3.2.11 on 2022-01-20 20:38

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0007_auto_20220118_2227"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="groupassociation",
            name="unique_group_association",
        ),
        migrations.RemoveConstraint(
            model_name="landscapegroup",
            name="unique_landscape_group",
        ),
        migrations.RemoveConstraint(
            model_name="membership",
            name="unique_membership",
        ),
        migrations.AlterField(
            model_name="group",
            name="slug",
            field=models.SlugField(blank=True, editable=False, max_length=250),
        ),
        migrations.AlterField(
            model_name="landscape",
            name="slug",
            field=models.SlugField(blank=True, editable=False, max_length=250),
        ),
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(max_length=254),
        ),
        migrations.AddConstraint(
            model_name="groupassociation",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("parent_group", "child_group"),
                name="unique_group_association",
            ),
        ),
        migrations.AddConstraint(
            model_name="landscape",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("slug",),
                name="unique_active_slug",
            ),
        ),
        migrations.AddConstraint(
            model_name="landscapegroup",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("group", "landscape"),
                name="unique_active_landscape_group",
            ),
        ),
        migrations.AddConstraint(
            model_name="membership",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("group", "user"),
                name="unique_active_membership",
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("email",),
                name="unique_active_email",
            ),
        ),
    ]
