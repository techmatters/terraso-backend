from django.db import migrations, models

from apps.core.geo import calculate_geojson_polygon_area


def calculate_area(apps, schema_editor):
    Landscape = apps.get_model("core", "Landscape")
    missing_area = Landscape.objects.filter(area_polygon__isnull=False, area_scalar_m2__isnull=True)
    for landscape in missing_area:
        landscape.area_scalar = calculate_geojson_polygon_area
    Landscape.objects.bulk_update(missing_area, ["area_scalar_m2"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0015_landscape_area_scalar"),
    ]

    operations = [migrations.RunPython(calculate_area)]
