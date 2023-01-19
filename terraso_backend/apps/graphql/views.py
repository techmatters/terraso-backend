from django.views.generic import TemplateView
from graphene_django.views import GraphQLView

from apps.auth.mixins import AuthenticationRequiredMixin


class TerrasoGraphQLView(AuthenticationRequiredMixin, GraphQLView):
    def get_auth_enabled(self):
        return True


class TerrasoGraphQLDocs(TemplateView):
    template_name = "docs.html"
