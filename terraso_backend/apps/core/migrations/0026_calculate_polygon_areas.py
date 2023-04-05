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

from django.db import migrations, models

from apps.core.gis.utils import calculate_geojson_feature_area


def calculate_area(apps, schema_editor):
    Landscape = apps.get_model("core", "Landscape")
    missing_area = Landscape.objects.filter(area_polygon__isnull=False, area_scalar_m2__isnull=True)
    for landscape in missing_area:
        landscape.area_scalar_m2 = calculate_geojson_feature_area(landscape.area_polygon)
    Landscape.objects.bulk_update(missing_area, ["area_scalar_m2"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0025_landscape_area_scalar"),
    ]

    operations = [migrations.RunPython(calculate_area)]
