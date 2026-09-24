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

"""Management command alternative to the admin import form.

Does exactly what the admin form does, but runs in-process so long
imports (large maps, slow storage) are never bounded by the HTTP/gunicorn
worker timeout.
"""

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.story_map.import_service import DEFAULT_SOURCE_API_BASE_URL, import_story_map


class Command(BaseCommand):
    help = (
        "Import a published story map from another Terraso environment: copies the "
        "published configuration, chapter media and layer GeoJSON into this "
        "environment's storage, owned by a local user."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "story_map_url",
            help="Public URL of the published story map in the source environment",
        )
        parser.add_argument(
            "--owner-email",
            required=True,
            help="Email of an existing local user who will own the imported story map",
        )
        parser.add_argument(
            "--source-api-base-url",
            default=DEFAULT_SOURCE_API_BASE_URL,
            help="Base URL of the source environment's backend (default: %(default)s)",
        )

    def handle(self, *args, **options):
        self.stdout.write("Fetching and copying story map data (this can take a while)...")
        try:
            story_map, warnings = import_story_map(
                story_map_url=options["story_map_url"],
                source_api_base_url=options["source_api_base_url"],
                owner_email=options["owner_email"],
            )
        except ValidationError as exc:
            message_dict = getattr(exc, "message_dict", None) or {None: exc.messages}
            messages = "; ".join(
                "; ".join(
                    str(message)
                    for message in (
                        field_errors if isinstance(field_errors, (list, tuple)) else [field_errors]
                    )
                )
                for field_errors in message_dict.values()
            )
            raise CommandError(f"Import failed: {messages}") from exc

        for warning in warnings:
            self.stdout.write(self.style.WARNING(str(warning)))

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported '{story_map.title}' (id={story_map.pk}, "
                f"owner={story_map.created_by.email})"
            )
        )
        self.stdout.write("The imported story map is a draft; publish it from the web UI.")
