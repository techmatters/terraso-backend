from apps.core.models import Group, Landscape, LandscapeGroup

from .base_airtable import BaseAirtableCommand


class Command(BaseAirtableCommand):
    help = "Import sample data from AirTable Landscapes table"

    def handle(self, *args, **kwargs):
        self.api_key = self.get_airtable_api_key(**kwargs)

        landscape_records = self.fetch_landscape_records()

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
                self.stdout.write(self.style.SUCCESS(f"Successfully created {landscape}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"Successfully updated {landscape}"))
