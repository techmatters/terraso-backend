# Mapbox API calls
import json

import requests
from django.conf import settings

API_HOST = "https://api.mapbox.com"
USERNAME = settings.MAPBOX_USERNAME
TOKEN = settings.MAPBOX_ACCESS_TOKEN


def create_tileset(id, geojson, name, description):
    tileset_source_id = id
    response, status_code = send_tileset_source(geojson, tileset_source_id)
    if status_code != 200:
        print(f"Error creating tileset source: {response}")
        raise Exception("Error creating tileset source")

    recipe_json = {
        "recipe": {
            "version": 1,
            "layers": {"layer1": {"source": response["id"], "minzoom": 0, "maxzoom": 14}},
        },
        "name": name,
        "description": description,
        "attribution": [{"text": "(c) Terraso", "link": ""}],
    }

    tileset_id = id
    response, status_code = send_tileset(recipe_json, tileset_id)

    if status_code != 200:
        print(f"Error creating tileset: {response}")
        raise Exception("Error creating tileset")

    response, status_code = publish_tileset(tileset_id)

    if status_code != 200:
        print(f"Error publishing tileset: {response}")
        raise Exception("Error publishing tileset")

    return tileset_id


def send_tileset_source(geojson, id):
    line_delimited_geojson = "\n".join([json.dumps(feature) for feature in geojson["features"]])

    file = open("test.ndjson", "w")
    file.write(line_delimited_geojson)

    url = f"{API_HOST}/tilesets/v1/sources/{USERNAME}/{id}?access_token={TOKEN}"
    multipart_data = [("file", ("test.ndjson", line_delimited_geojson, "text/plain"))]

    r = requests.post(url, files=multipart_data)
    response = r.json()
    status_code = r.status_code
    return response, status_code


def send_tileset(recipe_json, id):
    url = f"{API_HOST}/tilesets/v1/{USERNAME}.{id}?access_token={TOKEN}"
    headers = {
        "Content-Type": "application/json",
    }
    r = requests.post(url, json=recipe_json, headers=headers)
    response = r.json()
    status_code = r.status_code
    return response, status_code


def publish_tileset(id):
    url = f"{API_HOST}/tilesets/v1/{USERNAME}.{id}/publish?access_token={TOKEN}"
    r = requests.post(url)
    response = r.json()
    status_code = r.status_code
    return response, status_code


def get_publish_status(id, job_id):
    url = f"{API_HOST}/tilesets/v1/{USERNAME}.{id}/jobs/{job_id}?access_token={TOKEN}"
    r = requests.get(url)
    response = r.json()
    status_code = r.status_code
    return response, status_code
