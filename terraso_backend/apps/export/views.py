# Copyright © 2021-2025 Technology Matters
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

from django.contrib.auth import get_user_model
from django.http import HttpResponse, JsonResponse

from .formatters import sites_to_csv
from .services import fetch_all_sites, fetch_site_data
from .transformers import transform_site_data


def simple_report(request):
    format = request.GET.get("format", "csv")
    # project_id = request.GET.get("project_id", "90f32c23-3dfb-4c31-80c3-27dca6ef1cc3") # johannes local
    project_id = request.GET.get("project_id", "860ec581-3bdb-4846-a149-222d7991e866")  # derek server
    # user_id = request.GET.get("user_id", "4f2301b4-208f-45f9-98e1-7bac2610c231") # johannes local
    user_id = request.GET.get("user_id", "f8953ff0-6398-49b0-a246-92568fc7d804")  # derek server

    # getting list of projects for a user requires authentication
    User = get_user_model()
    service_user = User.objects.get(email="derek@techmatters.org")
    request.user = service_user

    # Fetch all sites for the project
    sites_list = fetch_all_sites(project_id, request, 1)

    # Fetch detailed data for each site and transform it
    all_sites = []
    for site in sites_list:
        site_data = fetch_site_data(site["id"], request, 1)
        transformed_site = transform_site_data(site_data, request, 50)
        all_sites.append(transformed_site)

    if format == "json":
        return JsonResponse({"sites": all_sites})

    return HttpResponse(sites_to_csv(all_sites), content_type="text/csv")