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

"""Import a published story map from another environment.

Retrieves a story map's published configuration from a remote Terraso
backend (anonymously; only published maps are readable), copies its media
and GeoJSON blobs into this environment's S3 buckets, and creates the
corresponding rows here owned by a local user.

Blob copying (downloads from the source environment, uploads to this one)
runs concurrently before any DB writes; the DB transaction afterwards only
rewrites the config and inserts rows, so failures leave at most orphaned
S3 blobs behind, never half-linked rows.
"""

import ipaddress
import json
import secrets
import socket
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote, urlparse

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.core.models import User
from apps.shared_data.models.data_entries import DataEntry
from apps.shared_data.models.visualization_config import VisualizationConfig
from apps.shared_data.services import data_entry_upload_service, geojson_upload_service
from apps.story_map.models.story_maps import StoryMap
from apps.story_map.services import story_map_media_upload_service

DEFAULT_SOURCE_API_BASE_URL = "https://api.terraso.org"

GRAPHQL_TIMEOUT_SECONDS = 30
DOWNLOAD_TIMEOUT_SECONDS = 60
DOWNLOAD_CHUNK_BYTES = 1024 * 1024
MAX_COPY_WORKERS = 8

# Fields of the frontend-merged layer dict that belong to the source
# VisualizationConfig *node* rather than to the VC's serialized
# configuration, so the remainder can be stored as the new VC's
# configuration. Keep in sync with the merge in
# web/src/storyMap/storyMapService.js (fetchDataLayers / addMapLayer).
LAYER_NODE_FIELDS = frozenset(
    {
        "id",
        "slug",
        "readableId",
        "createdAt",
        "createdBy",
        "title",
        "description",
        "mapboxTilesetId",
        "mapboxTilesetStatus",
        "geojsonSignedUrl",
        "geojson",
        "dataEntry",
        "tilesetId",
        "processing",
        "isRestricted",
    }
)

# Frontend-only bookkeeping keys found in stored layer dicts, which must
# not leak into imported configs (they describe the source environment).
STALE_LAYER_FIELDS = (
    "dataEntry",
    "processing",
    "isRestricted",
    "tilesetId",
    "createdAt",
    "createdBy",
)


def extract_story_map_lookup(story_map_url):
    """Return (story_map_id, slug) from a web client story map URL.

    Accepts full URLs (e.g. https://app.terraso.org/tools/story-maps/<id>/<slug>)
    or bare path fragments, with or without a trailing /embed.
    """
    if not story_map_url:
        return None

    normalized = unquote(story_map_url.strip())
    parsed = urlparse(normalized)
    candidate_path = parsed.path if parsed.scheme or parsed.netloc else normalized
    path_segments = [segment for segment in candidate_path.split("/") if segment]

    if "story-maps" in path_segments:
        story_maps_index = path_segments.index("story-maps")
        path_segments = path_segments[story_maps_index + 1 :]

    if not path_segments:
        return None

    story_map_id = path_segments[0]
    slug = path_segments[1] if len(path_segments) > 1 else None
    if slug == "embed":  # .../<id>/<slug>/embed
        slug = None
    return story_map_id, slug


def _fetch_published_story_map(backend_base_url, story_map_id, slug):
    url = f"{backend_base_url.rstrip('/')}/graphql/"
    query = """
query importedStoryMap($slug: String, $storyMapId: String!) {
  storyMaps(slug: $slug, storyMapId: $storyMapId) {
    edges {
      node {
        title
        slug
        storyMapId
        isPublished
        publishedConfiguration
      }
    }
  }
}
"""
    try:
        response = requests.post(
            url,
            json={"query": query, "variables": {"slug": slug, "storyMapId": story_map_id}},
            timeout=GRAPHQL_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise ValidationError(
            {"source_api_base_url": _("Could not reach the source backend: %(error)s")}
            % {"error": str(exc)}
        ) from exc

    if response.status_code != 200:
        raise ValidationError(
            {"source_api_base_url": _("Source backend returned HTTP %(status)s")}
            % {"status": response.status_code}
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise ValidationError(
            {"source_api_base_url": _("Source backend returned a non-JSON response")}
        ) from exc

    errors = (payload or {}).get("errors")
    if errors:
        message = errors[0].get("message", "unknown error")
        raise ValidationError(
            {"story_map_url": _("Source backend error: %(message)s") % {"message": message}}
        )

    data = (payload or {}).get("data") or {}
    edges = data.get("storyMaps", {}).get("edges") or []
    if not edges:
        raise ValidationError(
            {"story_map_url": _("No story map found at that URL (is it published?)")}
        )

    node = edges[0]["node"]
    published_configuration = node.get("publishedConfiguration")
    if not node.get("isPublished") or not published_configuration:
        raise ValidationError({"story_map_url": _("That story map has no published configuration")})

    try:
        if isinstance(published_configuration, str):
            published_configuration = json.loads(published_configuration)
    except ValueError as exc:
        raise ValidationError(
            {"story_map_url": _("The source story map's configuration is not valid JSON")}
        ) from exc

    return node, published_configuration


def _assert_public_http_url(url, error_field):
    """Reject non-http(s) and privately-addressed URLs before fetching.

    Download URLs come from remotely-authored story map content, so block
    requests to internal/link-local addresses (SSRF).
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not (parsed.scheme == "https" or settings.DEBUG):
        raise ValidationError({error_field: _("Only https URLs can be fetched")})

    hostname = parsed.hostname
    if not hostname:
        raise ValidationError({error_field: _("Invalid URL")})

    try:
        addr_infos = socket.getaddrinfo(
            hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            proto=socket.IPPROTO_TCP,
        )
    except OSError as exc:
        raise ValidationError(
            {error_field: _("Could not resolve host %(host)s: %(error)s")}
            % {"host": hostname, "error": str(exc)}
        ) from exc

    for addr_info in addr_infos:
        ip = ipaddress.ip_address(addr_info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ValidationError({error_field: _("Refusing to fetch from a non-public address")})


def _download_bytes(url, what):
    """Download a blob, enforcing the configured upload size limit."""
    _assert_public_http_url(url, "story_map_url")
    max_size = settings.MEDIA_UPLOAD_MAX_FILE_SIZE
    try:
        with requests.get(url, timeout=DOWNLOAD_TIMEOUT_SECONDS, stream=True) as response:
            if response.status_code != 200:
                raise ValidationError(
                    {"story_map_url": _("Failed to download %(what)s: HTTP %(status)s")}
                    % {"what": what, "status": response.status_code}
                )
            chunks = []
            received = 0
            for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_BYTES):
                received += len(chunk)
                if received > max_size:
                    raise ValidationError(
                        {"story_map_url": _("%(what)s exceeds the %(max)d MB size limit")}
                        % {"what": what.capitalize(), "max": max_size // 1000000}
                    )
                chunks.append(chunk)
            return b"".join(chunks)
    except requests.RequestException as exc:
        raise ValidationError(
            {"story_map_url": _("Failed to download %(what)s: %(error)s")}
            % {"what": what, "error": str(exc)}
        ) from exc


def _is_relative_storage_path(url):
    """S3-stored media is recorded as a relative path like '<user>/<uuid>'."""
    parsed = urlparse(url or "")
    return parsed.scheme == "" and parsed.netloc == ""


def _iter_media_blobs(config):
    """Yield the media/featuredImage dicts that point at source S3 storage."""
    for chapter in config.get("chapters", []):
        media = chapter.get("media")
        if media:
            yield media
    featured_image = config.get("featuredImage")
    if featured_image:
        yield featured_image


def _collect_download_jobs(config):
    """Collect (what, signed_url) pairs for every blob the config references.

    Media dicts with an absolute URL (embedded/external media) need no copy
    and are skipped. Media with a relative URL but no signed URL cannot be
    copied and fails the import.
    """
    jobs = []
    for media in _iter_media_blobs(config):
        url = media.get("url")
        if not url or not _is_relative_storage_path(url):
            continue
        if not media.get("signedUrl"):
            raise ValidationError(
                {
                    "story_map_url": _(
                        "Cannot import chapter media: the source backend did not provide a "
                        "signed URL"
                    )
                }
            )
        jobs.append(("chapter media", media["signedUrl"]))

    for layer in config.get("dataLayers", {}).values():
        if isinstance(layer, dict) and layer.get("geojsonSignedUrl"):
            jobs.append(("map layer GeoJSON", layer["geojsonSignedUrl"]))

    return jobs


def _run_concurrently(jobs):
    """Run (key, thunk) jobs on a thread pool; re-raise the first failure."""
    if not jobs:
        return []

    def run(job):
        key, thunk = job
        return key, thunk()

    with ThreadPoolExecutor(max_workers=min(MAX_COPY_WORKERS, len(jobs))) as executor:
        return list(executor.map(run, jobs))


def _copy_media_and_geojson(config, owner):
    """Download every remote blob and upload it to this environment's S3.

    Runs outside the DB transaction. Returns:
      media_paths:  {source signed URL: new local storage path}
      geojson:      {layer key: {vc_id, slug, readable_id, title, content,
                                 s3_key, data_entry}}
      warnings:     human-readable notes about things that were skipped
    Layers without a GeoJSON source (e.g. legacy Mapbox-tileset-only layers)
    are absent from `geojson` and produce a warning instead.
    """
    downloads = {}
    for what, signed_url in _collect_download_jobs(config):
        downloads.setdefault(signed_url, (what, lambda u=signed_url, w=what: _download_bytes(u, w)))

    contents = dict(
        _run_concurrently([(signed_url, thunk) for signed_url, (_, thunk) in downloads.items()])
    )

    uploads = []
    geojson = {}
    for signed_url, content in contents.items():
        if downloads[signed_url][0] != "chapter media":
            continue
        uploads.append(
            (
                ("media", signed_url),
                lambda c=content: story_map_media_upload_service.upload_file_get_path(
                    str(owner.id), ContentFile(c), file_name=str(uuid.uuid4())
                ),
            )
        )

    for key, layer in config.get("dataLayers", {}).items():
        if not isinstance(layer, dict):
            continue
        if layer.get("geojsonSignedUrl"):
            content = contents[layer["geojsonSignedUrl"]]
        elif layer.get("geojson") is not None:
            content = _validate_inline_geojson(layer["geojson"])
        else:
            continue  # e.g. legacy Mapbox-tileset-only layer
        vc_id = uuid.uuid4()
        title = (layer.get("title") or "Imported map layer").strip()[:128]
        geojson[key] = {
            "vc_id": vc_id,
            "slug": slugify(title),
            "readable_id": secrets.token_hex(4),
            "title": title,
            "content": content,
        }
        uploads.append(
            (
                ("s3_key", key),
                lambda v=vc_id, c=content: geojson_upload_service.upload_file_get_path(
                    str(v), ContentFile(c), file_name=f"{v}.geojson"
                ),
            )
        )
        uploads.append(
            (
                ("data_entry", key),
                lambda t=title, c=content: data_entry_upload_service.upload_file(
                    str(owner.id),
                    ContentFile(c),
                    file_name=_data_entry_file_name(t),
                ),
            )
        )

    media_paths = {}
    for job_key, result in _run_concurrently(uploads):
        kind, identity = job_key
        if kind == "media":
            media_paths[identity] = result
        else:
            geojson[identity][kind] = result

    warnings = [
        _("Map layer '%(title)s' has no GeoJSON to copy (legacy Mapbox tileset only)")
        % {"title": layer.get("title") or key}
        for key, layer in config.get("dataLayers", {}).items()
        if isinstance(layer, dict)
        and key not in geojson
        and layer.get("geojsonSignedUrl") is None
        and layer.get("geojson") is None
    ]
    return media_paths, geojson, warnings


def _validate_inline_geojson(geojson_value):
    """Serialize and validate an inline geojson value from the config."""
    if not isinstance(geojson_value, dict):
        raise ValidationError(
            {"story_map_url": _("A map layer's inline GeoJSON is not a JSON object")}
        )
    content = json.dumps(geojson_value).encode("utf-8")
    if len(content) > settings.MEDIA_UPLOAD_MAX_FILE_SIZE:
        raise ValidationError(
            {"story_map_url": _("A map layer's inline GeoJSON exceeds the size limit")}
        )
    return content


def _data_entry_file_name(title):
    """Sane .geojson file name; slugify can be empty for non-ASCII titles."""
    return f"{slugify(title) or uuid.uuid4().hex}.geojson"


def _rewrite_config(config, media_paths, geojson):
    """Point the config at the locally copied blobs, dropping source URLs.

    Rekeys config['dataLayers'] to the new VC ids and rekeys `geojson` to
    match, so DB row creation (which maps each dataLayers entry to its
    copied blob) lines up. Returns nothing.
    """
    for media in _iter_media_blobs(config):
        signed_url = media.get("signedUrl")
        if signed_url in media_paths:
            media["url"] = media_paths[signed_url]
            media.pop("signedUrl", None)

    vc_id_map = {}
    rekeyed_data_layers = {}
    rekeyed_geojson = {}
    for key, layer in config.get("dataLayers", {}).items():
        if not isinstance(layer, dict):
            rekeyed_data_layers[key] = layer
            continue
        for stale in STALE_LAYER_FIELDS:
            layer.pop(stale, None)
        copied = geojson.get(key)
        if not copied:
            continue  # e.g. legacy Mapbox-tileset-only layer
        old_id = layer.get("id")
        new_id = str(copied["vc_id"])
        if old_id:
            vc_id_map[old_id] = new_id
        layer["id"] = new_id
        layer["slug"] = copied["slug"]
        layer["readableId"] = copied["readable_id"]
        layer["geojsonSignedUrl"] = geojson_upload_service.get_signed_url(copied["s3_key"])
        layer.pop("geojson", None)
        rekeyed_data_layers[new_id] = layer
        rekeyed_geojson[new_id] = copied
    config["dataLayers"] = rekeyed_data_layers
    geojson.clear()
    geojson.update(rekeyed_geojson)

    _remap_layer_references(config, vc_id_map)


def _remap_layer_references(config, vc_id_map):
    """Point chapters' data-layer references at the re-created VCs.

    Chapters reference their layer via `dataLayerConfigId` and via mapbox
    layer ids of the form '<vc-id>-<layer-type>' in onChapterEnter/
    onChapterExit entries — both must be rewritten or chapter transitions
    silently stop working.
    """
    if not vc_id_map:
        return

    def remap_transition(transition):
        if not isinstance(transition, dict):
            return
        old_id = transition.get("dataLayerConfigId")
        if old_id and old_id in vc_id_map:
            transition["dataLayerConfigId"] = vc_id_map[old_id]
        for key in ("onChapterEnter", "onChapterExit"):
            for event in transition.get(key) or []:
                layer_id = event.get("layer") or ""
                for old_id, new_id in vc_id_map.items():
                    if layer_id.startswith(f"{old_id}-"):
                        event["layer"] = f"{new_id}{layer_id[len(old_id) :]}"
                        break

    for chapter in config.get("chapters", []):
        remap_transition(chapter)
    remap_transition(config.get("titleTransition"))


def _imported_title(original_title):
    """Mark the import in the title: '<original> - Imported At YYYY-MM-DD HH:mm'.

    The suffix makes the import identifiable in lists and keeps the slug
    distinct from the source map's; the original title is truncated so the
    result fits the 128-char field.
    """
    suffix = f" - Imported At {timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M')}"
    max_length = StoryMap._meta.get_field("title").max_length
    return f"{original_title.strip()[: max_length - len(suffix)]}{suffix}"


def _create_rows(config, owner, story_map, geojson):
    for key, layer in config.get("dataLayers", {}).items():
        copied = geojson.get(key)
        if not copied:
            continue
        data_entry = DataEntry.objects.create(
            name=copied["title"],
            entry_type=DataEntry.ENTRY_TYPE_FILE,
            resource_type="geojson",
            url=copied["data_entry"],
            size=len(copied["content"]),
            created_by=owner,
        )
        VisualizationConfig.objects.create(
            id=copied["vc_id"],
            title=copied["title"],
            description=layer.get("description"),
            configuration={
                field: value for field, value in layer.items() if field not in LAYER_NODE_FIELDS
            },
            geojson_s3_key=copied["s3_key"],
            data_entry=data_entry,
            readable_id=copied["readable_id"],
            created_by=owner,
            owner=story_map,
        )


def import_story_map(*, story_map_url, source_api_base_url=None, owner_email):
    """Import a published story map from a remote environment.

    Returns (story_map, warnings). Raises ValidationError on any failure;
    all DB writes are rolled back in that case. S3 blobs uploaded before the
    failure may be orphaned, matching the existing upload views' behaviour.
    """
    lookup = extract_story_map_lookup(story_map_url)
    if not lookup:
        raise ValidationError({"story_map_url": _("Enter a valid story map URL")})
    story_map_id, slug = lookup

    base_url = source_api_base_url or DEFAULT_SOURCE_API_BASE_URL
    _assert_public_http_url(base_url, "source_api_base_url")

    try:
        owner = User.objects.get(email__iexact=owner_email.strip())
    except User.DoesNotExist as exc:
        raise ValidationError(
            {"owner_email": _("No user found with that email in this environment")}
        ) from exc
    except User.MultipleObjectsReturned as exc:
        raise ValidationError({"owner_email": _("Multiple users share that email")}) from exc

    node, config = _fetch_published_story_map(base_url, story_map_id, slug)

    media_paths, geojson, warnings = _copy_media_and_geojson(config, owner)

    # Keep the config's title in sync with the row title: the frontend
    # derives the StoryMap.title it publishes from config.title, so a
    # diverging config value would override the stamped row title on
    # publish.
    imported_title = _imported_title(node["title"])
    config["title"] = imported_title

    with transaction.atomic():
        story_map = StoryMap.objects.create(
            story_map_id=secrets.token_hex(4),
            created_by=owner,
            title=imported_title,
            is_published=False,
            featured=False,
        )
        _rewrite_config(config, media_paths, geojson)
        _create_rows(config, owner, story_map, geojson)
        story_map.configuration = config
        story_map.save(update_fields=["configuration"])

    return story_map, warnings
