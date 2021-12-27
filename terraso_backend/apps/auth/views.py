import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views import View

from .providers import AppleProvider, GoogleProvider
from .services import AccountService, JWTService

User = get_user_model()


class AuthorizeView(View):
    provider = None

    def get(self, request, *args, **kwargs):
        return JsonResponse({"request_url": self.provider.login_url() if self.provider else ""})


class GoogleAuthorizeView(AuthorizeView):
    provider = GoogleProvider


class AppleAuthorizeView(AuthorizeView):
    provider = AppleProvider


class AbstractCallbackView(View):
    def get(self, request, *args, **kwargs):
        self.authorization_code = self.request.GET.get("code")
        self.error = self.request.GET.get("error")

        return self.process_callback()

    def post(self, request, *args, **kwargs):
        self.authorization_code = self.request.POST.get("code")
        self.error = self.request.POST.get("error")

        return self.process_callback()

    def process_callback(self):
        if self.error:
            return HttpResponse(f"Error: {self.error}", status=400)

        if not self.authorization_code:
            return HttpResponse("Error: no authorization code informed", status=400)

        jwt_service = JWTService()

        try:
            user = self.process_signup()
            access_token = jwt_service.create_access_token(user)
            refresh_token = jwt_service.create_refresh_token(user)
        except Exception as exc:
            return HttpResponse(f"Error: {exc}", status=400)

        response = HttpResponseRedirect(settings.WEB_CLIENT_URL)
        response.set_cookie("atoken", access_token, domain=settings.AUTH_COOKIE_DOMAIN)
        response.set_cookie("rtoken", refresh_token, domain=settings.AUTH_COOKIE_DOMAIN)

        return response

    def process_signup(self):
        raise NotImplementedError("AbstractCallbackView must be inherited.")


class GoogleCallbackView(AbstractCallbackView):
    def process_signup(self):
        return AccountService().sign_up_with_google(self.authorization_code)


class AppleCallbackView(AbstractCallbackView):
    def process_signup(self):
        try:
            apple_user_data = json.loads(self.request.POST.get("user", "{}"))
        except json.JSONDecodeError:
            raise Exception("couldn't parse User data from Apple")

        first_name = apple_user_data.get("name", {}).get("firstName", "")
        last_name = apple_user_data.get("name", {}).get("lastName", "")

        return AccountService().sign_up_with_apple(
            self.authorization_code, first_name=first_name, last_name=last_name
        )


class RefreshAccessTokenView(View):
    def post(self, request, *args, **kwargs):
        try:
            request_data = json.loads(request.body)
        except json.decoder.JSONDecodeError:
            return JsonResponse({"error": "The request expects a json body"}, status=400)

        try:
            refresh_token = request_data["refresh_token"]
        except KeyError:
            return JsonResponse(
                {"error": "The request expects a 'refresh_token' parameter"}, status=400
            )

        jwt_service = JWTService()

        try:
            refresh_payload = jwt_service.verify_token(refresh_token)
        except Exception as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        try:
            user = User.objects.get(id=refresh_payload["sub"])
        except User.DoesNotExist:
            return JsonResponse({"error": "User not found"}, status=400)

        if not user.is_active:
            return JsonResponse({"error": "User not found"}, status=400)

        access_token = jwt_service.create_access_token(user)
        refresh_token = jwt_service.create_refresh_token(user)

        return JsonResponse(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
            }
        )


class CheckUserView(View):
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthenticated request."}, status=401)

        return JsonResponse(
            {
                "user": {
                    "email": request.user.email,
                    "first_name": request.user.first_name,
                    "last_name": request.user.last_name,
                }
            }
        )
