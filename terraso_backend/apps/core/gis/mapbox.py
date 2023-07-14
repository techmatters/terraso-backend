# Copyright © 2023 Technology Matters
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
import json

import requests
from django.conf import settings

API_URL = settings.MAPBOX_API_URL
USERNAME = settings.MAPBOX_USERNAME
TOKEN = settings.MAPBOX_ACCESS_TOKEN


def create_tileset(id, geojson, name, description):
    tileset_source_id = id
    response, status_code = _post_tileset_source(geojson, tileset_source_id)
    if status_code != 200:
        raise Exception(
            "Received error sending post request to create tileset source. Response=", response
        )

    recipe_json = {
        "recipe": {
            "version": 1,
            "layers": {id: {"source": response["id"], "minzoom": 0, "maxzoom": 14}},
        },
        "name": name,
        "description": description,
        "attribution": [{"text": "© 2023 Terraso", "link": ""}],
    }

    tileset_id = id
    response, status_code = _post_tileset(recipe_json, tileset_id)

    if status_code != 200:
        raise Exception(
            "Received error sending post request to create tileset. Response=", response
        )

    response, status_code = _publish_tileset(tileset_id)

    if status_code != 200:
        raise Exception(
            "Received error sending post request to publish tileset. Response=", response
        )

    return tileset_id


def remove_tileset(id):
    response, status_code = _delete_tileset(id)
    if status_code != 200:
        raise Exception(
            "Received error sending delete request to delete tileset. Response=", response
        )

    response, status_code = _delete_tileset_source(id)
    if status_code != 204:
        raise Exception(
            "Received error sending delete request to delete tileset source. Response=", response
        )

    return True


def get_publish_status(id):
    url = f"{API_URL}/tilesets/v1/{USERNAME}.{id}/jobs?stage=success&access_token={TOKEN}"
    response = requests.get(url)
    response_json = response.json()
    status_code = response.status_code
    if status_code != 200:
        return False
    return len(response_json) > 0


def _post_tileset_source(geojson, id):
    line_delimited_geojson = "\n".join([json.dumps(feature) for feature in geojson["features"]])

    url = f"{API_URL}/tilesets/v1/sources/{USERNAME}/{id}?access_token={TOKEN}"
    multipart_data = [("file", ("test.ndjson", line_delimited_geojson, "text/plain"))]

    response = requests.post(url, files=multipart_data)
    response_json = response.json()
    status_code = response.status_code
    return response_json, status_code


def _delete_tileset_source(id):
    url = f"{API_URL}/tilesets/v1/sources/{USERNAME}/{id}?access_token={TOKEN}"
    response = requests.delete(url)
    status_code = response.status_code
    return None, status_code


def _post_tileset(recipe_json, id):
    url = f"{API_URL}/tilesets/v1/{USERNAME}.{id}?access_token={TOKEN}"
    headers = {
        "Content-Type": "application/json",
    }
    response = requests.post(url, json=recipe_json, headers=headers)
    response_json = response.json()
    status_code = response.status_code
    return response_json, status_code


def _delete_tileset(id):
    url = f"{API_URL}/tilesets/v1/{USERNAME}.{id}?access_token={TOKEN}"
    response = requests.delete(url)
    status_code = response.status_code
    return None, status_code


def _publish_tileset(id):
    url = f"{API_URL}/tilesets/v1/{USERNAME}.{id}/publish?access_token={TOKEN}"
    response = requests.post(url)
    response_json = response.json()
    status_code = response.status_code
    return response_json, status_code
