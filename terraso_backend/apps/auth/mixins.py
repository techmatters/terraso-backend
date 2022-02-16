import structlog
from django.http.response import JsonResponse

logger = structlog.get_logger(__name__)


class AuthenticationRequiredMixin:
    def get_auth_enabled(self):
        return True

    def dispatch(self, request, *args, **kwargs):
        if self.get_auth_enabled() and not request.user.is_authenticated:
            logger.warning("Unauthenticated request to authentication required resource")
            return JsonResponse({"error": "Unauthenticated request"}, status=401)

        return super().dispatch(request, *args, **kwargs)
