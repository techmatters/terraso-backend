from graphene_django.views import GraphQLView

from apps.auth.mixins import AuthenticationRequiredMixin


class TerrasoGraphQLView(AuthenticationRequiredMixin, GraphQLView):
    pass
