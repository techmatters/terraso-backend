import httpx

from apps.core.models import Landscape

from ._base_airtable import BaseAirtableCommand

GEOJSON_COLUMN_NAME = "Polygon (geojson)"


class Command(BaseAirtableCommand):
    help = "Import Landscape boundaries polygon (GeoJSON) from AirTable Landscapes table"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("--force_override", type=bool, default=False)

    def handle(self, *args, **kwargs):
        self.api_key = self.get_airtable_api_key(**kwargs)
        force_override = kwargs.get("force_override")

        landscape_records = self.fetch_landscape_records()

        for landscape_record in landscape_records:
            landscape_data = landscape_record["fields"]

            if not landscape_data.get("Co-Design Partner", False):
                continue

            landscape_name = landscape_data.get("Landscape Name")
            geojson = self._get_geojson(landscape_data)

            if not geojson:
                self.stdout.write(self.style.WARNING(f"GeoJSON not found for: {landscape_name}"))
                continue

            try:
                landscape = Landscape.objects.get(name=landscape_name)
            except Landscape.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Landscape not found: {landscape_name}"))
                continue

            if landscape.area_polygon and not force_override:
                msg = f"{landscape.slug} has a polygon. Use --force_override=true to update."
                self.stdout.write(self.style.WARNING(msg))
                continue

            landscape.area_polygon = geojson
            landscape.save()

            self.stdout.write(
                self.style.SUCCESS(f"GeoJSON successfully imported for {landscape.slug}")
            )

    def _get_geojson(self, landscape_data):
        geojson_attachments = landscape_data.get(GEOJSON_COLUMN_NAME)

        if not geojson_attachments:
            return

        geojson_url = geojson_attachments[0]["url"]

        try:
            geojson_response = httpx.get(geojson_url)
        except httpx.RequestError as e:
            self.stdout.write(
                self.style.ERROR(f"An error occurred while requesting {e.request.url!r}.")
            )
            return

        try:
            geojson_response.raise_for_status()
        except httpx.HTTPStatusError as e:
            self.stdout.write(
                self.style.ERROR(
                    f"Error {e.response.status_code} while requesting {e.request.url!r}."
                )
            )
            return

        return geojson_response.json()
