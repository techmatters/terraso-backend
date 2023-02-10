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

import json
import uuid
from dataclasses import asdict
from datetime import datetime

import rules
import structlog
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import IntegrityError
from django.http import JsonResponse
from django.utils import timezone
from django.views.generic.edit import FormView

from apps.auth.mixins import AuthenticationRequiredMixin
from apps.core.exceptions import ErrorContext, ErrorMessage

from .models import StoryMap
from .services import story_map_media_upload_service

logger = structlog.get_logger(__name__)


class StoryMapAddView(AuthenticationRequiredMixin, FormView):
    def post(self, request, **kwargs):
        form_data = request.POST.copy()

        config = json.loads(form_data["configuration"])

        try:
            story_map = StoryMap.objects.create(
                created_by=request.user,
                title=form_data["title"],
                is_published=form_data["is_published"] == "true",
                configuration=handle_config_media(config, None, request),
                published_at=timezone.make_aware(datetime.now(), timezone.get_current_timezone())
                if form_data["is_published"] == "true"
                else None,
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

        story_map.configuration = handle_config_media(new_config, story_map.configuration, request)
        try:
            story_map.save()
        except IntegrityError as exc:
            return handle_integrity_error(exc)

        return JsonResponse(story_map.to_dict(), status=201)


def handle_config_media(new_config, current_config, request):
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
                    "Error deleting media file",
                    extra={"media_path": media_path, "error": str(e)},
                )

    return new_config


def handle_integrity_error(exc):
    logger.info(
        "Attempt to mutate an model, but it's not unique",
        extra={"model": "StoryMap", "integrity_error": exc},
    )

    validation_error = ValidationError(
        message={
            NON_FIELD_ERRORS: ValidationError(
                message="This StoryMap already exists",
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
