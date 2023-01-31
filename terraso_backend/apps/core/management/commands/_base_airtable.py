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

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand

AT_LANDSCAPES_ENDPOINT = "https://api.airtable.com/v0/appIE3c0ExjlY2N7l/Landscapes"


class BaseAirtableCommand(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--airtable_api_key", type=str, default="")

    def handle(self, *args, **kwargs):
        raise NotImplementedError()

    def get_airtable_api_key(self, **kwargs):
        api_key = kwargs.get("airtable_api_key")

        if not api_key:
            api_key = settings.AIRTABLE_API_KEY

        assert api_key, "AirTable API key is necessary to load sample data."

        return api_key

    def fetch_landscape_records(self):
        response = httpx.get(
            AT_LANDSCAPES_ENDPOINT, headers={"Authorization": f"Bearer {self.api_key}"}
        )
        response.raise_for_status()
        return response.json()["records"]
