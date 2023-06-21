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
from datetime import datetime

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
from apps.storage.file_utils import has_multiple_files, is_file_upload_oversized

from .forms import StoryMapForm
from .models import StoryMap
from .services import story_map_media_upload_service

logger = structlog.get_logger(__name__)


class StoryMapAddView(AuthenticationRequiredMixin, FormView):
    def post(self, request, **kwargs):
        form_data = request.POST.copy()

        config = json.loads(form_data["configuration"])

        form_data["created_by"] = request.user
        form_data["is_published"] = form_data["is_published"] == "true"
        form_data["published_at"] = (
            timezone.make_aware(datetime.now(), timezone.get_current_timezone())
            if form_data["is_published"]
            else None
        )

        entry_form = StoryMapForm(data=form_data)
        if not entry_form.is_valid():
            error_messages = get_error_messages(entry_form.errors.as_data())
            return JsonResponse(
                {"errors": [{"message": [asdict(e) for e in error_messages]}]}, status=400
            )
        if has_multiple_files(request.FILES.getlist("files")):
            error_message = ErrorMessage(
                code="More than one file uploaded",
                context=ErrorContext(model="StoryMap", field="files"),
            )
            return JsonResponse({"errors": [{"message": [asdict(error_message)]}]}, status=400)

        if is_file_upload_oversized(request.FILES.getlist("files"), MEDIA_UPLOAD_MAX_FILE_SIZE):
            error_message = ErrorMessage(
                code="File size exceeds 10 MB",
                context=ErrorContext(model="StoryMap", field="files"),
            )
            return JsonResponse({"errors": [{"message": [asdict(error_message)]}]}, status=400)

        if invalid_media_type(config):
            error_message = ErrorMessage(
                code="Invalid Media Type",
                context=ErrorContext(model="StoryMap", field="configuration"),
            )
            return JsonResponse({"errors": [{"message": [asdict(error_message)]}]}, status=400)

        if "chapters" in config:
            for chapter in config["chapters"]:
                media = chapter.get("media")
                if not (
                    media
                    and (media["type"].startswith("image")
                         or media["type"].startswith("audio")
                         or media["type"].startswith("video"))
                ):
                    logger.info("Warning: invalid media type")
                    error_message = ErrorMessage(
                        code="Invalid Media Type",
                        context=ErrorContext(model="StoryMap", field=NON_FIELD_ERRORS)
                    )
                    return JsonResponse({"errors": [{
                        "message": [asdict(error_message)]}]}, status=400)
        try:
            story_map = StoryMap.objects.create(
                story_map_id=secrets.token_hex(4),
                created_by=form_data["created_by"],
                title=form_data["title"],
                is_published=form_data["is_published"],
                configuration=handle_config_media(config, None, request),
                published_at=form_data["published_at"],
            )
        except IntegrityError as exc:
            return handle_integrity_error(exc)

        return JsonResponse(story_map.to_dict(), status=201)


class StoryMapUpdateView(AuthenticationRequiredMixin, FormView):
    def post(self, request, **kwargs):
        user = request.user
        form_data = request.POST.copy()

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

        story_map.title = form_data["title"]

        if form_data["is_published"] == "true" and not story_map.is_published:
            story_map.published_at = timezone.make_aware(
                datetime.now(), timezone.get_current_timezone()
            )

        story_map.is_published = form_data["is_published"] == "true"

        new_config = json.loads(form_data["configuration"])

        if invalid_media_type(new_config):
            error_message = ErrorMessage(
                code="Invalid Media Type",
                context=ErrorContext(model="StoryMap", field="configuration"),
            )
            return JsonResponse({"errors": [{"message": [asdict(error_message)]}]}, status=400)
        if has_multiple_files(request.FILES.getlist("files")):
            error_message = ErrorMessage(
                code="Uploaded more than one file",
                context=ErrorContext(model="StoryMap", field="files"),
            )
            return JsonResponse({"errors": [{"message": [asdict(error_message)]}]}, status=400)
        if is_file_upload_oversized(request.FILES.getlist("files"), MEDIA_UPLOAD_MAX_FILE_SIZE):
            error_message = ErrorMessage(
                code="File size exceeds 10 MB",
                context=ErrorContext(model="StoryMap", field="files"),
            )
            return JsonResponse({"errors": [{"message": [asdict(error_message)]}]}, status=400)

        story_map.configuration = handle_config_media(new_config, story_map.configuration, request)

        entry_form = StoryMapForm(data=story_map.to_dict())

        if not entry_form.is_valid():
            error_messages = get_error_messages(entry_form.errors.as_data())
            return JsonResponse(
                {"errors": [{"message": [asdict(e) for e in error_messages]}]}, status=400
            )

        try:
            story_map.save()
        except IntegrityError as exc:
            return handle_integrity_error(exc)

        return JsonResponse(story_map.to_dict(), status=201)


def handle_config_media(new_config, current_config, request):
    if "chapters" in new_config:
        for chapter in new_config["chapters"]:
            media = chapter.get("media")
            if media and "contentId" in media:
                file_id = media["contentId"]
                matching_file = next(
                    (file for file in request.FILES.getlist("files") if file.name == file_id), None
                )
                if matching_file:
                    url = story_map_media_upload_service.upload_file_get_path(
                        str(request.user.id),
                        matching_file,
                        file_name=uuid.uuid4(),
                    )
                    chapter["media"] = {"url": url, "type": media["type"]}

    if (current_config is None) or (not current_config.get("chapters")):
        return new_config

    # Delete changed media
    current_media = [
        chapter["media"]["url"]
        for chapter in current_config["chapters"]
        if chapter.get("media") and "url" in chapter["media"]
    ]
    new_media = [
        chapter["media"]["url"]
        for chapter in new_config["chapters"]
        if chapter.get("media") and "url" in chapter["media"]
    ]

    for media_path in current_media:
        if media_path not in new_media:
            try:
                story_map_media_upload_service.delete_file(media_path)
            except Exception as e:
                logger.exception(
                    "Unable to delete media file",
                    extra={"media_path": media_path, "error": str(e)},
                )

    return new_config


def invalid_media_type(config):
    if "chapters" in config:
        for chapter in config["chapters"]:
            media = chapter.get("media")
            if not (media and media["type"].startswith(("image", "audio", "video"))):
                return True
            return False


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
