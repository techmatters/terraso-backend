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
import secrets
import uuid
from dataclasses import asdict

import rules
import structlog
from config.settings import MEDIA_UPLOAD_MAX_FILE_SIZE
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import IntegrityError
from django.http import JsonResponse
from django.utils import timezone
from django.views.generic.edit import FormView

from apps.auth.mixins import AuthenticationRequiredMixin
from apps.core.exceptions import ErrorContext, ErrorMessage
from apps.shared_data.models.visualization_config import VisualizationConfig
from apps.shared_data.services import geojson_upload_service
from apps.storage.file_utils import is_file_upload_oversized

from .forms import StoryMapForm
from .models import StoryMap
from .services import story_map_media_upload_service

logger = structlog.get_logger(__name__)


def _chapter_media_items(chapter):
    if not isinstance(chapter, dict):
        raise ValidationError("Invalid Media Type")

    if "mediaItems" in chapter:
        items = chapter["mediaItems"]
        if not isinstance(items, list):
            raise ValidationError("Invalid Media Type")
    else:
        media = chapter.get("media")
        items = [] if media is None else [media]

    if any(
        not isinstance(item, dict)
        or not isinstance(item.get("type"), str)
        or not item["type"].startswith(("image", "audio", "video", "embedded"))
        for item in items
    ):
        raise ValidationError("Invalid Media Type")

    return items


def refresh_story_map_config_urls(config):
    if "chapters" in config:
        for chapter in config["chapters"]:
            for media in _chapter_media_items(chapter):
                if "url" in media and media["type"].startswith(("image", "audio", "video")):
                    media["signedUrl"] = story_map_media_upload_service.get_signed_url(media["url"])

    if "featuredImage" in config:
        featured_image = config["featuredImage"]
        if featured_image and "url" in featured_image:
            signed_url = story_map_media_upload_service.get_signed_url(featured_image["url"])
            config["featuredImage"]["signedUrl"] = signed_url

    if "dataLayers" in config:
        data_layers = config["dataLayers"]
        layer_ids = [
            layer.get("id")
            for layer in data_layers.values()
            if isinstance(layer, dict) and layer.get("id")
        ]
        if layer_ids:
            vcs = {
                str(vc.id): vc
                for vc in VisualizationConfig.objects.filter(id__in=layer_ids).only(
                    "id", "geojson_s3_key"
                )
            }
            for layer in data_layers.values():
                if isinstance(layer, dict) and layer.get("id"):
                    vc = vcs.get(str(layer["id"]))
                    if vc and vc.geojson_s3_key:
                        layer["geojsonSignedUrl"] = geojson_upload_service.get_signed_url(
                            vc.geojson_s3_key
                        )

    return config


class StoryMapAddView(AuthenticationRequiredMixin, FormView):
    def post(self, request, **kwargs):
        form_data = request.POST.copy()

        config = json.loads(form_data["configuration"])

        publish = form_data["publish"] == "true"

        form_data["created_by"] = request.user
        form_data["is_published"] = publish
        form_data["published_at"] = timezone.now() if form_data["is_published"] else None

        entry_form = StoryMapForm(data=form_data)
        if not entry_form.is_valid():
            error_messages = get_error_messages(entry_form.errors.as_data())
            return JsonResponse(
                {"errors": [{"message": [asdict(e) for e in error_messages]}]}, status=400
            )

        if is_file_upload_oversized(request.FILES.getlist("files"), MEDIA_UPLOAD_MAX_FILE_SIZE):
            error_message = ErrorMessage(
                code="File size exceeds 10 MB",
                context=ErrorContext(model="StoryMap", field="files"),
            )
            return JsonResponse({"errors": [{"message": [asdict(error_message)]}]}, status=400)

        if not is_valid_media_type(config):
            error_message = ErrorMessage(
                code="Invalid Media Type",
                context=ErrorContext(model="StoryMap", field="configuration"),
            )
            return JsonResponse({"errors": [{"message": [asdict(error_message)]}]}, status=400)

        try:
            configuration = handle_config_media(config, None, request)

            story_map = StoryMap.objects.create(
                story_map_id=secrets.token_hex(4),
                created_by=form_data["created_by"],
                title=form_data["title"],
                is_published=form_data["is_published"],
                configuration=configuration,
                published_configuration=configuration if publish else None,
                published_at=form_data["published_at"],
            )
        except IntegrityError as exc:
            return handle_integrity_error(exc)

        refresh_story_map_config_urls(story_map.configuration)

        return JsonResponse(story_map.to_dict(), status=201)


class StoryMapUpdateView(AuthenticationRequiredMixin, FormView):
    def post(self, request, **kwargs):
        user = request.user
        form_data = request.POST.copy()

        publish = form_data.get("publish") == "true"
        unpublish = form_data.get("unpublish") == "true"

        story_map = StoryMap.objects.get(id=form_data["id"])

        if not rules.test_rule("allowed_to_change_story_map", user, story_map):
            logger.info(
                "Attempt to update a StoryMap, but user lacks permission",
                extra={"user_id": user.pk, "story_map_id": str(story_map.id)},
            )
            error_message = ErrorMessage(
                code="update", context=ErrorContext(model="StoryMap", field=NON_FIELD_ERRORS)
            )
            return JsonResponse({"errors": [{"message": [asdict(error_message)]}]}, status=400)

        if publish and unpublish:
            error_message = ErrorMessage(
                code="Cannot publish and unpublish simultaneously",
                context=ErrorContext(model="StoryMap", field=NON_FIELD_ERRORS),
            )
            return JsonResponse({"errors": [{"message": [asdict(error_message)]}]}, status=400)

        if unpublish:
            story_map.is_published = False
            story_map.published_at = None
            story_map.save(update_fields=["is_published", "published_at", "updated_at"])
            return JsonResponse(story_map.to_dict(), status=201)

        story_map.title = form_data["title"]

        if publish:
            story_map.published_at = timezone.now()
            story_map.is_published = True

        new_config = json.loads(form_data["configuration"])

        if not is_valid_media_type(new_config):
            error_message = ErrorMessage(
                code="Invalid Media Type",
                context=ErrorContext(model="StoryMap", field="configuration"),
            )
            return JsonResponse({"errors": [{"message": [asdict(error_message)]}]}, status=400)

        if is_file_upload_oversized(request.FILES.getlist("files"), MEDIA_UPLOAD_MAX_FILE_SIZE):
            error_message = ErrorMessage(
                code="File size exceeds 10 MB",
                context=ErrorContext(model="StoryMap", field="files"),
            )
            return JsonResponse({"errors": [{"message": [asdict(error_message)]}]}, status=400)

        story_map.configuration = handle_config_media(new_config, story_map, request)
        if publish:
            story_map.published_configuration = story_map.configuration

        entry_form = StoryMapForm(data=story_map.to_dict())

        if not entry_form.is_valid():
            error_messages = get_error_messages(entry_form.errors.as_data())
            return JsonResponse(
                {"errors": [{"message": [asdict(e) for e in error_messages]}]}, status=400
            )

        try:
            # Draft saves must not restore publication state read before an unpublish.
            update_fields = ["title", "slug", "configuration", "updated_at"]
            if publish:
                update_fields.extend(["is_published", "published_at", "published_configuration"])
            story_map.save(update_fields=update_fields)
        except IntegrityError as exc:
            return handle_integrity_error(exc)

        refresh_story_map_config_urls(story_map.configuration)

        return JsonResponse(story_map.to_dict(), status=201)


def _upload_file(request, content_id):
    """Upload a file and return its URL."""
    matching_file = next(
        (file for file in request.FILES.getlist("files") if file.name == content_id),
        None,
    )
    if matching_file:
        return story_map_media_upload_service.upload_file_get_path(
            str(request.user.id),
            matching_file,
            file_name=uuid.uuid4(),
        )
    return None


def _extract_media_urls(config):
    chapter_urls = [
        media["url"]
        for chapter in config.get("chapters", [])
        for media in _chapter_media_items(chapter)
        if "url" in media and media["type"].startswith(("image", "audio", "video"))
    ]

    featured_url = (
        [config["featuredImage"]["url"]]
        if config.get("featuredImage") and "url" in config["featuredImage"]
        else []
    )

    return chapter_urls + featured_url


def _upload_chapter_media(config, request):
    for chapter in config.get("chapters", []):
        for media in _chapter_media_items(chapter):
            if "contentId" in media and not media["type"].startswith("embedded"):
                url = _upload_file(request, media["contentId"])
                if url:
                    media["url"] = url
                    del media["contentId"]


def _upload_featured_image(config, request):
    featured_image = config.get("featuredImage")
    if not featured_image or "contentId" not in featured_image:
        return

    url = _upload_file(request, featured_image["contentId"])
    if not url:
        return

    new_featured_image = {"url": url}
    if "description" in featured_image:
        new_featured_image["description"] = featured_image["description"]
    config["featuredImage"] = new_featured_image


def _cleanup_unused_media(current_config, new_config, published_config):
    current_media = _extract_media_urls(current_config)

    active_configs = [new_config]
    if published_config:
        active_configs.append(published_config)

    new_media = []
    for config in active_configs:
        new_media.extend(_extract_media_urls(config))

    for media_path in current_media:
        if media_path not in new_media:
            try:
                story_map_media_upload_service.delete_file(media_path)
            except Exception as e:
                logger.exception(
                    "Unable to delete media file",
                    extra={"media_path": media_path, "error": str(e)},
                )


def handle_config_media(new_config, story_map, request):
    """
    Handle media files for story map configuration.

    1. Upload new media files to S3
    2. Update configuration with uploaded URLs
    3. Delete unused media files from S3
    """
    _upload_chapter_media(new_config, request)
    _upload_featured_image(new_config, request)

    if story_map and story_map.configuration:
        _cleanup_unused_media(
            story_map.configuration, new_config, story_map.published_configuration
        )

    return new_config


def is_valid_media_type(config):
    if "chapters" in config:
        if not isinstance(config["chapters"], list):
            return False
        try:
            for chapter in config["chapters"]:
                _chapter_media_items(chapter)
        except ValidationError:
            return False
        return True


def handle_integrity_error(exc):
    logger.info(
        "Attempt to mutate an model, but it's not unique because of the title unique constraint",
        extra={"model": "StoryMap", "integrity_error": exc},
    )

    validation_error = ValidationError(
        message={
            NON_FIELD_ERRORS: ValidationError(
                message="This StoryMap title already exists",
                code="unique",
            )
        },
    )
    error_messages = from_validation_error(validation_error)
    return JsonResponse({"errors": [{"message": [asdict(e) for e in error_messages]}]}, status=400)


def from_validation_error(validation_error):
    error_messages = []
    for field, validation_errors in validation_error.error_dict.items():
        for error in validation_errors:
            error_messages.append(
                ErrorMessage(
                    code=error.code,
                    context=ErrorContext(model="StoryMap", field=field),
                )
            )
    return error_messages


def get_error_messages(validation_errors):
    error_messages = []

    for field, errors in validation_errors.items():
        for error in errors:
            error_messages.append(
                ErrorMessage(
                    code=error.code,
                    context=ErrorContext(
                        model="StoryMap",
                        field=field,
                        extra=error.message,
                    ),
                )
            )

    return error_messages
