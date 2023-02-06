﻿# Copyright © 2021-2023 Technology Matters
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

import structlog
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import IntegrityError
from django.http import JsonResponse
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
                configuration=handle_config_media(config, request),
            )
        except IntegrityError as exc:
            return handle_integrity_error(exc)

        return JsonResponse(story_map.to_dict(), status=201)


class StoryMapUpdateView(AuthenticationRequiredMixin, FormView):
    def post(self, request, **kwargs):
        form_data = request.POST.copy()

        story_map = StoryMap.objects.get(id=form_data["id"])
        story_map.created_by = request.user
        story_map.title = form_data["title"]

        new_config = json.loads(form_data["configuration"])

        story_map.configuration = handle_config_media(new_config, story_map.configuration, request)
        try:
            story_map.save()
        except IntegrityError as exc:
            return handle_integrity_error(exc)

        return JsonResponse(story_map.to_dict(), status=201)


def handle_config_media(new_config, current_config, request):
    for chapter in new_config["chapters"]:
        if "media" in chapter and "contentId" in chapter["media"]:
            file_id = chapter["media"]["contentId"]
            for file in request.FILES.getlist("files"):
                if file.name == file_id:
                    url = story_map_media_upload_service.upload_file_get_path(
                        str(request.user.id),
                        file,
                        file_name=uuid.uuid4(),
                    )
                    chapter["media"] = {"url": url, "type": chapter["media"]["type"]}
                    break

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
            story_map_media_upload_service.delete_file(media_path)

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
