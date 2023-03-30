# Copyright © 2021-2023 Technology Matters
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see https://www.gnu.org/licenses/.

from django.conf import settings
from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from apps.auth.middleware import auth_not_required

from .views import TerrasoGraphQLDocs, TerrasoGraphQLView

app_name = "apps.graphql"

urlpatterns = [
    path("docs", TerrasoGraphQLDocs.as_view()),
]

if settings.DEBUG:
    urlpatterns.append(
        path("", csrf_exempt(auth_not_required(TerrasoGraphQLView.as_view(graphiql=True))))
    )
else:
    urlpatterns.append(path("", csrf_exempt(auth_not_required(TerrasoGraphQLView.as_view()))))
