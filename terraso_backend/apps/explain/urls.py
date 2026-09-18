# Copyright © 2025 Technology Matters
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

# Standalone "explain report" endpoint. It renders the soil-ID scoring trace
# (from the export app's `.json?explain=true`) as a self-contained HTML page.
#
# Deliberately isolated from apps.export: it depends on export only through that
# public URL contract (it self-fetches over HTTP), so it can be deleted — or
# lifted to a separate process/host — without untangling any imports. To remove:
# delete apps/explain/, drop the include() in config/urls.py, and delete the
# redirect hook in apps/export/html_pages.py.

from django.urls import path
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt

from apps.auth.middleware import auth_optional

from . import views

app_name = "explain"

urlpatterns = [
    # Mirrors the export token path (…/token/<type>/<token>/<name>.html) under a
    # separate prefix. The view reconstructs the sibling export .json?explain=true
    # URL from this path, so one route covers site/project/user_owned/user_all.
    #
    # auth_optional mirrors the export token views: this is a public endpoint
    # (authorized by the token in the path), so the JWT middleware must allow an
    # unauthenticated browser navigation through rather than 401-ing it.
    path(
        "token/<str:resource_type>/<str:token>/<str:name>.html",
        csrf_exempt(auth_optional(never_cache(views.explain_report))),
        name="explain-report",
    ),
]
