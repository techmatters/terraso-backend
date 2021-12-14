import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views import View

from .providers import AppleProvider, GoogleProvider
from .services import AccountService, JWTService

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
            jwt_service = JWTService()
            access_token = jwt_service.create_access_token(user)
            refresh_token = jwt_service.create_refresh_token(user)
        except Exception as exc:
            return HttpResponse(f"Error: {exc}", status=400)

        user_data = {
            "user": {
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "access_token": access_token,
                "refresh_token": refresh_token,
            },
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


class AppleCallbackView(View):
    def post(self, request, *args, **kwargs):
        authorization_code = request.POST.get("code")
        error = request.POST.get("error")

        if error:
            return HttpResponse(f"Error: {error}", status=400)

        if not authorization_code:
            return HttpResponse("Error: no authorization code informed", status=400)

        try:
            apple_user_data = json.loads(request.POST.get("user", "{}"))
            first_name = apple_user_data["name"]["firstName"]
            last_name = apple_user_data["name"]["lastName"]
        except json.JSONDecodeError:
            return HttpResponse("Error: couldn't parse User data from Apple", status=400)
        except KeyError:
            return HttpResponse("Error: couldn't get User name from Apple", status=400)

        try:
            user = AccountService().sign_up_with_apple(
                authorization_code, first_name=first_name, last_name=last_name
            )
        except Exception as exc:
            return HttpResponse(f"Error: {exc}", status=400)

        user_data = {
            "email": user.email,
            "user": {
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
        }

        response = HttpResponseRedirect(settings.WEB_CLIENT_URL)
        response.set_cookie(
            "user",
            json.dumps(user_data),
            domain=settings.AUTH_COOKIE_DOMAIN,
        )

        return response
