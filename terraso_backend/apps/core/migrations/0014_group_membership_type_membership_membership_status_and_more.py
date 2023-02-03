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

# Generated by Django 4.0.4 on 2022-06-14 17:40

from django.db import migrations, models

import apps.core.models.commons


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0013_group_deleted_by_cascade_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="group",
            name="membership_type",
            field=models.CharField(
                choices=[("open", "Open"), ("closed", "Closed")], default="open", max_length=32
            ),
        ),
        migrations.AddField(
            model_name="membership",
            name="membership_status",
            field=models.CharField(
                choices=[("approved", "Approved"), ("pending", "Pending")],
                default="approved",
                max_length=64,
            ),
        ),
        migrations.AlterField(
            model_name="group",
            name="name",
            field=models.CharField(
                max_length=128, unique=True, validators=[apps.core.models.commons.validate_name]
            ),
        ),
        migrations.AlterField(
            model_name="landscape",
            name="name",
            field=models.CharField(
                max_length=128, unique=True, validators=[apps.core.models.commons.validate_name]
            ),
        ),
    ]
