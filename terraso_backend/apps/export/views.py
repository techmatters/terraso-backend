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

from .fetch_data import fetch_site_data, fetch_soil_id
from .fetch_lists import fetch_all_sites, fetch_project_list, fetch_user_owned_sites
from .formatters import sites_to_csv
from .transformers import transform_site_data


def _setup_system_export_user(request):
    """Set up request with system export user and flag."""
    User = get_user_model()
    service_user = User.objects.get(email="system-export@terraso.org")
    request.user = service_user
    request.is_system_export = True


def _process_sites(site_ids, request):
    """
    Process a set of site IDs into full site data.
    Returns a sorted list of transformed sites with soil_id data.
    """
    all_sites = []
    for site_id in site_ids:
        site_data = fetch_site_data(site_id, request)
        transformed_site = transform_site_data(site_data, request)
        transformed_site["soil_id"] = fetch_soil_id(transformed_site, request)
        all_sites.append(transformed_site)

    # Sort sites by name
    all_sites.sort(key=lambda site: site.get("name", ""))
    return all_sites


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
    # System exports bypass user-based security checks
    # (Security will be implemented separately via export-specific permissions)
    _setup_system_export_user(request)

    # Fetch all site IDs for the project (returns a set)
    site_ids = fetch_all_sites(project_id, request)

    # Process sites (fetch details, transform, add soil_id, sort)
    all_sites = _process_sites(site_ids, request)

    return _export_sites_response(all_sites, format, project_name)


def site_export(request, site_id, site_name, format):
    # System exports bypass user-based security checks
    # (Security will be implemented separately via export-specific permissions)
    _setup_system_export_user(request)

    # Process single site
    site_ids = {site_id}
    all_sites = _process_sites(site_ids, request)

    return _export_sites_response(all_sites, format, site_name)


def user_owned_sites_export(request, user_id, user_name, format):
    """Export all sites owned by a specific user (not in any project)."""
    # System exports bypass user-based security checks
    # (Security will be implemented separately via export-specific permissions)
    _setup_system_export_user(request)

    # Fetch site IDs owned by the user (returns a set)
    site_ids = fetch_user_owned_sites(user_id, request)

    # Process sites (fetch details, transform, add soil_id, sort)
    all_sites = _process_sites(site_ids, request)

    return _export_sites_response(all_sites, format, f"{user_name}_owned_sites")


def user_all_sites_export(request, user_id, user_name, format):
    """Export all sites owned by user plus all sites in projects where user is a member."""
    # System exports bypass user-based security checks
    # (Security will be implemented separately via export-specific permissions)
    _setup_system_export_user(request)

    # Fetch site IDs owned by the user (returns a set)
    site_ids = fetch_user_owned_sites(user_id, request)

    # Fetch all project IDs where user is a member
    project_ids = fetch_project_list(user_id, request)

    # Add site IDs from each project (set union handles deduplication automatically)
    for project_id in project_ids:
        project_site_ids = fetch_all_sites(project_id, request)
        site_ids.update(project_site_ids)

    # Process sites (fetch details, transform, add soil_id, sort)
    all_sites = _process_sites(site_ids, request)

    return _export_sites_response(all_sites, format, f"{user_name}_and_projects")
