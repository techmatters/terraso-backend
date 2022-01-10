from django.http.response import JsonResponse


class AuthenticationRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"error": "Unauthenticated request"}, status=401
            )

        return super().dispatch(request, *args, **kwargs)
