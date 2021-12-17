import httpx
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.core.models import Group, Landscape, LandscapeGroup

AT_LANDSCAPES_ENDPOINT = "https://api.airtable.com/v0/appIE3c0ExjlY2N7l/Landscapes"


class Command(BaseCommand):
    help = "Import sample data from AirTable Landscapes table"

    def add_arguments(self, parser):
        parser.add_argument("--airtable_api_key", type=str, default="")

    def handle(self, *args, **kwargs):
        self.api_key = self._get_airtable_api_key(**kwargs)

        landscape_records = self._fetch_landscape_records()

        for landscape_record in landscape_records:
            landscape_data = landscape_record["fields"]

            if not landscape_data.get("Co-Design Partner", False):
                continue

            location = landscape_data.get("Continent", "")
            location += ", " + landscape_data.get("Country", "")

            landscape_name = landscape_data.get("Landscape Name")
            model_data = {
                "description": landscape_data.get("General Description", ""),
                "website": landscape_data.get("URL", ""),
                "location": location,
            }

            # Creates Landscape
            landscape, created = Landscape.objects.update_or_create(
                name=landscape_name, defaults=model_data
            )

            # Creates Landscape default group
            default_group, _ = Group.objects.update_or_create(name=f"{landscape_name} Group")
            landscape_group, _ = LandscapeGroup.objects.update_or_create(
                landscape=landscape,
                group=default_group,
                defaults={"is_default_landscape_group": True},
            )

            # Creates Partnership group
            partnership_name = landscape_data.get("Landscape Partnership Name")
            if partnership_name:
                group, _ = Group.objects.update_or_create(
                    name=partnership_name,
                    defaults={"description": landscape_data.get("General Description", "")},
                )
                landscape_group, _ = LandscapeGroup.objects.update_or_create(
                    landscape=landscape,
                    group=group,
                    defaults={"is_default_landscape_group": False},
                )

            # Creates Co Design Partner group
            co_design_partner_name = landscape_data.get("Co Design Partner Name (Group)")
            if co_design_partner_name:
                partner_group, _ = Group.objects.update_or_create(
                    name=co_design_partner_name,
                    defaults={"description": landscape_data.get("Group Description", "")},
                )
                landscape_group, _ = LandscapeGroup.objects.update_or_create(
                    landscape=landscape,
                    group=partner_group,
                    defaults={"is_default_landscape_group": False},
                )

            if created:
                self.stdout.write(self.style.SUCCESS(f"Sucessfully created {landscape}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"Sucessfully updated {landscape}"))

    def _get_airtable_api_key(self, **kwargs):
        api_key = kwargs.get("airtable_api_key")

        if not api_key:
            api_key = settings.AIRTABLE_API_KEY

        assert api_key, "AirTable API key is necessary to load sample data."

        return api_key

    def _fetch_landscape_records(self):
        response = httpx.get(
            AT_LANDSCAPES_ENDPOINT, headers={"Authorization": f"Bearer {self.api_key}"}
        )
        response.raise_for_status()
        return response.json()["records"]
