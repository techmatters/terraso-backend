# Copyright © 2023 Technology Matters
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

from django.db import migrations


def assign_unique_project_settings(apps, schema_editor):
    Project = apps.get_model("project_management", "Project")
    ProjectSettings = apps.get_model("project_management", "ProjectSettings")
    db_alias = schema_editor.connection.alias
    for project in Project.objects.using(db_alias).all():
        project.settings = ProjectSettings.objects.using(db_alias).create(project=project)
        project.save()


class Migration(migrations.Migration):
    dependencies = [
        ("project_management", "0010_projectsettings"),
    ]

    operations = [
        migrations.RunPython(
            code=assign_unique_project_settings, reverse_code=migrations.RunPython.noop
        ),
    ]
