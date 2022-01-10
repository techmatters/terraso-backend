from django.contrib.auth import get_user_model
from django.http import JsonResponse

from .exceptions import ExpiredTokenError
from .services import JWTService

User = get_user_model()


class JWTAuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        error_response = None
        user = None

        if not request.user or not request.user.is_authenticated:
            try:
                user = self._get_user_from_jwt(request)
            except ExpiredTokenError:
                error_response = JsonResponse({"error": "Forbidden"}, status=403)
            except Exception:
                error_response = JsonResponse({"error": "Unauthorized"}, status=401)

        if error_response:
            return error_response

        if user:
            request.user = user

        response = self.get_response(request)

        return response

    def _get_user_from_jwt(self, request):
        if not request:
            return None

        auth_header = request.META.get("HTTP_AUTHORIZATION")

        if not auth_header:
            return None

        auth_header_parts = auth_header.split()

        if len(auth_header_parts) != 2:
            return None

        token_type, token = auth_header_parts

        if token_type != "Bearer":
            return None

        decoded_payload = JWTService().verify_token(token)

        return self._get_user(decoded_payload["sub"])

    def _get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
