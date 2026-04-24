# Copyright © 2026 Technology Matters
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

import uuid

import apps.project_management.models.site_push_history
import django.db.models.deletion
import rules.contrib.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("project_management", "0029_alter_projectsettings_options"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SitePushHistory",
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
                ("site_changes", models.JSONField(encoder=apps.project_management.models.site_push_history.JSONEncoder)),
                (
                    "changed_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL
                    ),
                ),
                (
                    "site",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="project_management.site",
                    ),
                ),
                ("update_failure_reason", models.TextField(null=True)),
                ("update_succeeded", models.BooleanField(default=False)),
            ],
            options={
                "verbose_name_plural": "History: SitePushHistory",
                "ordering": ["created_at"],
                "get_latest_by": "-created_at",
                "abstract": False,
            },
            bases=(rules.contrib.models.RulesModelMixin, models.Model),
        ),
    ]
