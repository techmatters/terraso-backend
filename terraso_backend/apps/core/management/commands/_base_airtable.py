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
