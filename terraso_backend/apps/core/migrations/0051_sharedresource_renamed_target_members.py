# Copyright © 2024 Technology Matters
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


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0050_sharedresource_remove_none"),
    ]

    operations = [
        migrations.RunSQL(
            sql="UPDATE core_sharedresource SET share_access ='members' WHERE share_access='target_members';"
        ),
    ]
