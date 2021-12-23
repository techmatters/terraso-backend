from graphene_django.views import GraphQLView


class TerrasoGraphQLView(GraphQLView):
    def dispatch(self, request, *args, **kwargs):
        # TODO: uncomment following code when client ready for authentication
        #  if not request.user.is_authenticated:
        #      return JsonResponse(
        #          {"error": "Permission denied"}, status=403
        #      )

        return super().dispatch(request, *args, **kwargs)
