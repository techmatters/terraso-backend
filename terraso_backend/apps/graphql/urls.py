from django.conf import settings
from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from .views import TerrasoGraphQLView

app_name = "apps.graphql"

urlpatterns = [
    path("", csrf_exempt(TerrasoGraphQLView.as_view(graphiql=True))),
]

if settings.DEBUG:
    urlpatterns.append(path("", csrf_exempt(TerrasoGraphQLView.as_view(graphiql=True))))
else:
    urlpatterns.append(path("", csrf_exempt(TerrasoGraphQLView.as_view())))
