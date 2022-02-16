from django.views.generic import TemplateView
from graphene_django.views import GraphQLView


class TerrasoGraphQLView(GraphQLView):
    pass


class TerrasoGraphQLDocs(TemplateView):
    template_name = "docs.html"
