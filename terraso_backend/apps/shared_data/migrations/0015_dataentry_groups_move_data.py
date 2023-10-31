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

from django.conf import settings
from django.db import migrations


def data_entries_to_shared_resources(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    LandscapeGroup = apps.get_model("core", "LandscapeGroup")
    SharedResource = apps.get_model("core", "SharedResource")
    DataEntry = apps.get_model("shared_data", "DataEntry")
    data_entries = DataEntry.objects.all()
    for data_entry in data_entries:
        groups = data_entry.groups.all()
        for group in groups:
            landscape_group = LandscapeGroup.objects.filter(
                group=group, is_default_landscape_group=True
            ).first()
            if landscape_group is None:
                SharedResource.objects.create(
                    source_content_type=ContentType.objects.get_for_model(data_entry),
                    source_object_id=data_entry.id,
                    target_content_type=ContentType.objects.get_for_model(group),
                    target_object_id=group.id,
                )
            else:
                SharedResource.objects.create(
                    source_content_type=ContentType.objects.get_for_model(data_entry),
                    source_object_id=data_entry.id,
                    target_content_type=ContentType.objects.get_for_model(
                        landscape_group.landscape
                    ),
                    target_object_id=landscape_group.landscape.id,
                )


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0046_shared_resource"),
        ("shared_data", "0014_visualizationconfig_owner_null"),
    ]

    operations = [
        migrations.RunPython(data_entries_to_shared_resources),
    ]
