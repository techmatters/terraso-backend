import functools
import json

import structlog
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import login as dj_login
from django.contrib.auth import logout as dj_logout
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views import View

from .providers import AppleProvider, GoogleProvider
from .services import AccountService, JWTService

logger = structlog.get_logger(__name__)
User = get_user_model()
jwt_service = JWTService()


class AbstractAuthorizeView(View):
    def get(self, request, *args, **kwargs):
        state = request.GET.get("state")
        return JsonResponse({"request_url": self.provider.login_url(state=state)})

    @property
    def provider(self):
        return NotImplementedError("AbstractAuthorizeView must be inherited")


class GoogleAuthorizeView(AbstractAuthorizeView):
    @property
    def provider(self):
        return GoogleProvider


class AppleAuthorizeView(AbstractAuthorizeView):
    @property
    def provider(self):
        return AppleProvider


class AbstractCallbackView(View):
    def get(self, request, *args, **kwargs):
        self.authorization_code = self.request.GET.get("code")
        self.error = self.request.GET.get("error")
        self.state = self.request.GET.get("state", "")

        return self.process_callback()

    def post(self, request, *args, **kwargs):
        self.authorization_code = self.request.POST.get("code")
        self.error = self.request.POST.get("error")
        self.state = self.request.POST.get("state", "")

        return self.process_callback()

    def process_callback(self):
        if self.error:
            logger.error("Auth provider returned error on callback", extra={"error": self.error})
            return HttpResponse(f"Error: {self.error}", status=400)

        if not self.authorization_code:
            logger.error("No authorization code from auth provider on callback")
            return HttpResponse("Error: no authorization code informed", status=400)

        try:
            user, created_with_service = self.process_signup()
            access_token, refresh_token = terraso_login(self.request, user)
        except Exception as exc:
            logger.exception("Error attempting create access and refresh tokens")
            return HttpResponse(f"Error: {exc}", status=400)

        response = HttpResponseRedirect(f"{settings.WEB_CLIENT_URL}/{self.state}")
        response.set_cookie("atoken", access_token, domain=settings.AUTH_COOKIE_DOMAIN)
        response.set_cookie("rtoken", refresh_token, domain=settings.AUTH_COOKIE_DOMAIN)
        if created_with_service:
            # Set samesite to avoid warnings
            response.set_cookie("new_signup", created_with_service, samesite="Strict")

        return response

    def process_signup(self):
        raise NotImplementedError("AbstractCallbackView must be inherited.")


def record_creation(service):
    """A simple decorator to store if a new user has been created, and by which service"""

    def wrapper(f):
        @functools.wraps(f)
        def g(*args, **kwargs):
            user, created = f(*args, **kwargs)
            if created:
                return user, service
            else:
                return user, None

        return g

    return wrapper


class GoogleCallbackView(AbstractCallbackView):
    @record_creation("google")
    def process_signup(self):
        return AccountService().sign_up_with_google(self.authorization_code)


class AppleCallbackView(AbstractCallbackView):
    @record_creation("apple")
    def process_signup(self):
        user_obj = self.request.POST.get("user", "{}")
        try:
            apple_user_data = json.loads(user_obj)
        except json.JSONDecodeError:
            error_msg = "Couldn't parse User data from Apple"
            logger.error(error_msg, extra={"user_obj", user_obj})
            raise Exception(error_msg)

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
            logger.error("Failure parsing refresh token request body", extra={"body": request.body})
            return JsonResponse({"error": "The request expects a JSON body"}, status=400)

        try:
            refresh_token = request_data["refresh_token"]
        except KeyError:
            logger.error("Refresh token request without 'refresh_token' parameter")
            return JsonResponse(
                {"error": "The request expects a 'refresh_token' parameter"}, status=400
            )

        try:
            refresh_payload = jwt_service.verify_token(refresh_token)
        except Exception as exc:
            logger.exception("Error verifying refresh token")
            return JsonResponse({"error": str(exc)}, status=400)

        user_id = refresh_payload["sub"]
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.error("User from refresh token not found", extra={"user_id": user_id})
            return JsonResponse({"error": "User not found"}, status=400)

        if not user.is_active:
            logger.error(
                "User from refresh token is not active anymore", extra={"user_id": user_id}
            )
            return JsonResponse({"error": "User not found"}, status=400)

        access_token, refresh_token = terraso_login(self.request, user)

        return JsonResponse(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
            }
        )


class LogoutView(View):
    def post(self, request, *args, **kwargs):
        dj_logout(request)
        return HttpResponse("OK", status=200)


def terraso_login(request, user):
    access_token = jwt_service.create_access_token(user)
    refresh_token = jwt_service.create_refresh_token(user)
    dj_login(request, user, backend="django.contrib.auth.backends.ModelBackend")

    return access_token, refresh_token
