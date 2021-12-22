import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views import View

from .providers import AppleProvider, GoogleProvider
from .services import AccountService

User = get_user_model()


class GoogleAuthorizeView(View):
    def get(self, request, *args, **kwargs):
        return JsonResponse({"request_url": GoogleProvider.login_url()})


class GoogleCallbackView(View):
    def get(self, request, *args, **kwargs):
        authorization_code = request.GET.get("code")
        error = request.GET.get("error")

        if error:
            return HttpResponse(f"Error: {error}", status=400)

        if not authorization_code:
            return HttpResponse("Error: no authorization code informed", status=400)

        try:
            user = AccountService().sign_up_with_google(authorization_code)
        except Exception as exc:
            return HttpResponse(f"Error: {exc}", status=400)

        user_data = {
            "user": {
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            }
        }

        response = HttpResponseRedirect(settings.WEB_CLIENT_URL)
        response.set_cookie(
            "user",
            json.dumps(user_data),
            domain=settings.AUTH_COOKIE_DOMAIN,
        )

        return response


class AppleAuthorizeView(View):
    def get(self, request, *args, **kwargs):
        return JsonResponse({"request_url": AppleProvider.login_url()})

    def post(self, request, *args, **kwargs):
        try:
            request_data = json.loads(request.body)
        except json.decoder.JSONDecodeError:
            return JsonResponse(
                {"error": "The authorization request expects a JSON body"}, status=400
            )

        try:
            authorization_code = request_data["code"]
        except KeyError:
            return JsonResponse(
                {"error": "The authorization request expects a 'code' parameter"}, status=400
            )

        first_name = request_data.get("first_name", "")
        last_name = request_data.get("last_name", "")

        try:
            user = AccountService().sign_up_with_apple(
                authorization_code, first_name=first_name, last_name=last_name
            )
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
