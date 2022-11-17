from dataclasses import asdict

import rules
import structlog
from django.http import JsonResponse
from django.views.generic.edit import FormView

from apps.auth.mixins import AuthenticationRequiredMixin
from apps.core.exceptions import ErrorContext, ErrorMessage
from apps.storage.forms import LandscapeProfileImageForm

from .services import ProfileImageService

logger = structlog.get_logger(__name__)


class UserProfileImageView(AuthenticationRequiredMixin, FormView):
    def post(self, request, **kwargs):
        user = request.user
        profile_image_service = ProfileImageService()
        file_obj = request.FILES.get("file", "")

        user_id = str(user.id)
        try:
            user.profile_image = profile_image_service.upload_file(user_id, file_obj)
            user.save()
        except Exception:
            message = "Failed to upload profile image. User ID: {}".format(user_id)
            logger.exception(message)
            return JsonResponse({"error": message}, status=500)

        return JsonResponse({"message": "OK"})


class LandscapeProfileImageView(AuthenticationRequiredMixin, FormView):
    def post(self, request, **kwargs):
        user = request.user
        form_data = request.POST.copy()
        entry_form = LandscapeProfileImageForm(data=form_data, files=request.FILES)
        if not entry_form.is_valid():
            error_messages = get_error_messages("Landscape", entry_form.errors.as_data())
            return JsonResponse(
                {"errors": [{"message": [asdict(e) for e in error_messages]}]}, status=400
            )
        landscape = entry_form.cleaned_data["landscape"]

        if not rules.test_rule("allowed_to_change_landscape", user, landscape.id):
            message = "Not allowed to upload profile image. Landscape Slug: {}".format(
                landscape.slug
            )
            logger.exception(message)
            return JsonResponse({"errors": [{"message": [message]}]}, status=400)

        try:
            landscape.profile_image_description = entry_form.cleaned_data["description"]
            landscape.profile_image = entry_form.cleaned_data["url"]
            landscape.save()
        except Exception:
            message = "Failed to upload profile image. Landscape Slug: {}".format(landscape.slug)
            logger.exception(message)
            return JsonResponse({"errors": [{"message": [message]}]}, status=500)

        return JsonResponse({"message": "OK"})


def get_error_messages(model, validation_errors):
    error_messages = []

    for field, errors in validation_errors.items():
        for error in errors:
            error_messages.append(
                ErrorMessage(
                    code=error.code,
                    context=ErrorContext(
                        model=model,
                        field=field,
                        extra=error.message,
                    ),
                )
            )

    return error_messages
