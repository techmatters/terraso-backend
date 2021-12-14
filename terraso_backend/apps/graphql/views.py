from django.http import JsonResponse
from graphene_django.views import GraphQLView


class TerrasoGraphQLView(GraphQLView):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"error": "Permission denied"}, status=403
            )

        return super().dispatch(request, *args, **kwargs)
