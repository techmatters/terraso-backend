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

from urllib.parse import unquote

from django.contrib.auth import get_user_model
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest

from .formatters import sites_to_csv
from .services import fetch_all_sites, fetch_site_data, fetch_soil_id
from .transformers import transform_site_data


def _export_sites_response(all_sites, format, filename):
    """Helper function to generate export response for a list of sites."""
    # Validate format parameter
    if format not in ["csv", "json"]:
        return HttpResponseBadRequest(f"Unsupported format: {format}")

    # Decode URL-encoded characters in filename (e.g., %20 -> space)
    decoded_filename = unquote(filename)

    if format == "json":
        response = JsonResponse({"sites": all_sites})
        response["Content-Disposition"] = f'attachment; filename="{decoded_filename}.{format}"'
        return response

    response = HttpResponse(sites_to_csv(all_sites), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{decoded_filename}.{format}"'
    return response


def project_export(request, project_id, project_name, format):
    # getting list of projects for a user requires authentication
    User = get_user_model()
    service_user = User.objects.get(email="derek@techmatters.org")
    request.user = service_user

    soil_id = fetch_soil_id(41.6621642396362, 41.6621642396362, {
        "slope": 15,
        "surfaceCracks": "NO_CRACKING",
        "depthDependentData": [
            {
                "depthInterval": {
                    "start": 0,
                    "end": 5
                },
                "texture": "SANDY_LOAM",
                "rockFragmentVolume": "VOLUME_1_15",
                "colorLAB": { "L": 0.4, "A": 0.7, "B": 0.5 }
            }
        ]
    }, request)
    return JsonResponse({"soildatahere": soil_id})

    # Fetch all sites for the project using the ID
    sites_list = fetch_all_sites(project_id, request, 1)

    # Fetch detailed data for each site and transform it
    all_sites = []
    for site in sites_list:
        site_data = fetch_site_data(site["id"], request, 1)
        transformed_site = transform_site_data(site_data, request, 50)
        all_sites.append(transformed_site)

    return _export_sites_response(all_sites, format, project_name)


def site_export(request, site_id, site_name, format):
    # getting list of projects for a user requires authentication
    User = get_user_model()
    service_user = User.objects.get(email="derek@techmatters.org")
    request.user = service_user

    # Fetch detailed data for the specific site using the ID
    site_data = fetch_site_data(site_id, request, 1)
    transformed_site = transform_site_data(site_data, request, 50)
    all_sites = [transformed_site]

    return _export_sites_response(all_sites, format, site_name)
