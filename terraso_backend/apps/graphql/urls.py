from django.conf import settings
from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from .views import TerrasoGraphQLDocs, TerrasoGraphQLView

app_name = "apps.graphql"

urlpatterns = [
    path("docs", TerrasoGraphQLDocs.as_view()),
]

if settings.DEBUG:
    urlpatterns.append(path("", csrf_exempt(TerrasoGraphQLView.as_view(graphiql=True))))
else:
    urlpatterns.append(path("", csrf_exempt(TerrasoGraphQLView.as_view())))
