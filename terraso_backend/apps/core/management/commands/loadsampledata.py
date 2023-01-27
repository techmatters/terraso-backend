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

from apps.core.models import Group, Landscape, LandscapeGroup

from ._base_airtable import BaseAirtableCommand


class Command(BaseAirtableCommand):
    help = "Import sample data from AirTable Landscapes table"

    def handle(self, *args, **kwargs):
        self.api_key = self.get_airtable_api_key(**kwargs)

        landscape_records = self.fetch_landscape_records()

        for landscape_record in landscape_records:
            landscape_data = landscape_record["fields"]

            if not landscape_data.get("Co-Design Partner", False):
                continue

            location = landscape_data.get("Country", "")
            location += ", " + landscape_data.get("Continent", "")

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
