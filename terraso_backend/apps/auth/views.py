import json

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views import View

from .providers import GoogleProvider
from .services import AccountService

User = get_user_model()


class GoogleAuthorizeView(View):
    def get(self, request, *args, **kwargs):
        return JsonResponse({"request_url": GoogleProvider.login_url()})

    def post(self, request, *args, **kwargs):
        try:
            request_data = json.loads(request.body)
        except json.decoder.JSONDecodeError:
            return JsonResponse(
                {"error": "The authorization request expects a json body"}, status=400
            )

        try:
            authorization_code = request_data["code"]
        except KeyError:
            return JsonResponse(
                {"error": "The authorization request expects a 'code' parameter"}, status=400
            )

        try:
            user = AccountService().sign_up_with_google(authorization_code)
        except Exception as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        return JsonResponse(
            {
                "user": {
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
            }
        )
