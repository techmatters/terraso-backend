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
        raise Exception("Post Mapbox tileset source error", response)

    recipe_json = {
        "recipe": {
            "version": 1,
            "layers": {id: {"source": response["id"], "minzoom": 0, "maxzoom": 14}},
        },
        "name": name,
        "description": description,
        "attribution": [{"text": "© Terraso", "link": ""}],
    }

    tileset_id = id
    response, status_code = _post_tileset(recipe_json, tileset_id)

    if status_code != 200:
        raise Exception("Post Mapbox tileset error", response)

    response, status_code = _publish_tileset(tileset_id)

    if status_code != 200:
        raise Exception("Publish Mapbox tileset error", response)

    return tileset_id


def remove_tileset(id):
    response, status_code = _delete_tileset(id)
    if status_code != 200:
        raise Exception("Delete Mapbox tileset error", response)

    response, status_code = _delete_tileset_source(id)
    if status_code != 204:
        raise Exception("Delete Mapbox tileset source error", response)

    return True


def get_publish_status(id):
    url = f"{API_URL}/tilesets/v1/{USERNAME}.{id}/jobs?stage=success&access_token={TOKEN}"
    r = requests.get(url)
    response = r.json()
    status_code = r.status_code
    if status_code != 200:
        return False
    return len(response) > 0


def _post_tileset_source(geojson, id):
    line_delimited_geojson = "\n".join([json.dumps(feature) for feature in geojson["features"]])

    url = f"{API_URL}/tilesets/v1/sources/{USERNAME}/{id}?access_token={TOKEN}"
    multipart_data = [("file", ("test.ndjson", line_delimited_geojson, "text/plain"))]

    r = requests.post(url, files=multipart_data)
    response = r.json()
    status_code = r.status_code
    return response, status_code


def _delete_tileset_source(id):
    url = f"{API_URL}/tilesets/v1/sources/{USERNAME}/{id}?access_token={TOKEN}"
    r = requests.delete(url)
    status_code = r.status_code
    return None, status_code


def _post_tileset(recipe_json, id):
    url = f"{API_URL}/tilesets/v1/{USERNAME}.{id}?access_token={TOKEN}"
    headers = {
        "Content-Type": "application/json",
    }
    r = requests.post(url, json=recipe_json, headers=headers)
    response = r.json()
    status_code = r.status_code
    return response, status_code


def _delete_tileset(id):
    url = f"{API_URL}/tilesets/v1/{USERNAME}.{id}?access_token={TOKEN}"
    r = requests.delete(url)
    status_code = r.status_code
    return None, status_code


def _publish_tileset(id):
    url = f"{API_URL}/tilesets/v1/{USERNAME}.{id}/publish?access_token={TOKEN}"
    r = requests.post(url)
    response = r.json()
    status_code = r.status_code
    return response, status_code
