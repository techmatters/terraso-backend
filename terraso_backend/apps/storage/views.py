import structlog
from django.http import JsonResponse
from django.views.generic.edit import FormView

from apps.auth.mixins import AuthenticationRequiredMixin

from .services import ProfileImageService

logger = structlog.get_logger(__name__)


class ProfileImageView(AuthenticationRequiredMixin, FormView):
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
