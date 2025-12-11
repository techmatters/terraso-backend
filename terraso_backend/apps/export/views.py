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
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse

from .fetch_data import fetch_site_data, fetch_soil_id
from .fetch_lists import fetch_all_sites, fetch_project_list, fetch_user_owned_sites
from .formatters import sites_to_csv
from .html_pages import export_page_html, invalid_token_page
from .models import ExportToken
from .transformers import transform_site_data


def _resolve_export_token(token):
    """
    Resolve export token string to ExportToken object.
    Returns None if token not found.
    """
    try:
        return ExportToken.objects.get(token=token)
    except ExportToken.DoesNotExist:
        return None


def _setup_token_user(request, export_token):
    """Set up request with the user who owns the export token."""
    User = get_user_model()
    try:
        token_owner = User.objects.get(id=export_token.user_id)
    except User.DoesNotExist:
        raise RuntimeError(f"Token owner user not found: {export_token.user_id}")
    request.user = token_owner


def _process_sites(site_ids, request):
    """
    Process a set of site IDs into full site data.
    Returns a sorted list of transformed sites with soil_id data.
    """
    all_sites = []
    for site_id in site_ids:
        site_data = fetch_site_data(site_id, request)
        # Fetch soil_id BEFORE transformation since it needs original enum codes
        soil_id_data = fetch_soil_id(site_data, request)
        transformed_site = transform_site_data(site_data, request)
        transformed_site["soil_id"] = soil_id_data
        all_sites.append(transformed_site)

    # Sort sites by name
    all_sites.sort(key=lambda site: site.get("name", ""))
    return all_sites


def _strip_null_values(obj):
    """Recursively remove keys with None/null values from dicts."""
    if isinstance(obj, dict):
        return {k: _strip_null_values(v) for k, v in obj.items() if v is not None}
    elif isinstance(obj, list):
        return [_strip_null_values(item) for item in obj]
    return obj


def _export_sites_response(all_sites, format, filename):
    """Helper function to generate export response for a list of sites."""
    # Validate format parameter
    if format not in ["csv", "json"]:
        return HttpResponseBadRequest(f"Unsupported format: {format}")

    # Decode URL-encoded characters in filename (e.g., %20 -> space)
    decoded_filename = unquote(filename)

    if format == "json":
        cleaned_sites = _strip_null_values(all_sites)
        response = JsonResponse({"sites": cleaned_sites})
        response["Content-Disposition"] = f'attachment; filename="{decoded_filename}.{format}"'
        return response

    response = HttpResponse(sites_to_csv(all_sites), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{decoded_filename}.{format}"'
    return response


# Core business logic functions (shared by token-based and ID-based exports)


def _export_project_sites(project_id, request):
    """
    Core logic: Fetch and process all sites in a project.
    Returns sorted list of transformed site data.
    """
    site_ids = fetch_all_sites(project_id, request)
    return _process_sites(site_ids, request)


def _export_single_site(site_id, request):
    """
    Core logic: Fetch and process a single site.
    Returns sorted list of transformed site data (single item).
    """
    site_ids = {site_id}
    return _process_sites(site_ids, request)


def _export_user_owned_sites(user_id, request):
    """
    Core logic: Fetch and process user's unaffiliated sites only.
    Returns sorted list of transformed site data.
    """
    site_ids = fetch_user_owned_sites(user_id, request)
    return _process_sites(site_ids, request)


def _export_user_all_sites(user_id, request):
    """
    Core logic: Fetch and process user's owned sites plus all sites in user's projects.
    Returns sorted list of transformed site data.
    """
    # Fetch site IDs owned by the user (returns a set)
    site_ids = fetch_user_owned_sites(user_id, request)

    # Fetch all project IDs where user is a member
    project_ids = fetch_project_list(user_id, request)

    # Add site IDs from each project (set union handles deduplication automatically)
    for project_id in project_ids:
        project_site_ids = fetch_all_sites(project_id, request)
        site_ids.update(project_site_ids)

    return _process_sites(site_ids, request)


def project_export(request, project_token, project_name, format):
    """Export all sites in a project using export token (public access, no auth required)."""
    export_token = _resolve_export_token(project_token)
    if export_token is None:
        return invalid_token_page()
    if export_token.resource_type != "PROJECT":
        return HttpResponseBadRequest("Invalid token type for project export")

    _setup_token_user(request, export_token)

    # Use core business logic
    all_sites = _export_project_sites(export_token.resource_id, request)
    return _export_sites_response(all_sites, format, project_name)


def site_export(request, site_token, site_name, format):
    """Export a single site using export token (public access, no auth required)."""
    export_token = _resolve_export_token(site_token)
    if export_token is None:
        return invalid_token_page()
    if export_token.resource_type != "SITE":
        return HttpResponseBadRequest("Invalid token type for site export")

    _setup_token_user(request, export_token)

    # Use core business logic
    all_sites = _export_single_site(export_token.resource_id, request)
    return _export_sites_response(all_sites, format, site_name)


def user_owned_sites_export(request, user_token, user_name, format):
    """Export all sites owned by a specific user (not in any project) using export token (public access, no auth required)."""
    export_token = _resolve_export_token(user_token)
    if export_token is None:
        return invalid_token_page()
    if export_token.resource_type != "USER":
        return HttpResponseBadRequest("Invalid token type for user export")

    _setup_token_user(request, export_token)

    # Use core business logic
    all_sites = _export_user_owned_sites(export_token.resource_id, request)
    return _export_sites_response(all_sites, format, f"{user_name}_owned_sites")


def user_all_sites_export(request, user_token, user_name, format):
    """Export all sites owned by user plus all sites in projects where user is a member using export token (public access, no auth required)."""
    export_token = _resolve_export_token(user_token)
    if export_token is None:
        return invalid_token_page()
    if export_token.resource_type != "USER":
        return HttpResponseBadRequest("Invalid token type for user export")

    _setup_token_user(request, export_token)

    # Use core business logic
    all_sites = _export_user_all_sites(export_token.resource_id, request)
    return _export_sites_response(all_sites, format, f"{user_name}_and_projects")


# ID-based exports (authenticated, enforce permissions)


def project_export_by_id(request, project_id, project_name, format):
    """Export all sites in a project using project ID (authenticated, enforces permissions)."""
    if not request.user.is_authenticated:
        return HttpResponse("Authentication required", status=401)

    # Use core business logic - permissions enforced via GraphQL queries
    all_sites = _export_project_sites(project_id, request)
    return _export_sites_response(all_sites, format, project_name)


def site_export_by_id(request, site_id, site_name, format):
    """Export a single site using site ID (authenticated, enforces permissions)."""
    if not request.user.is_authenticated:
        return HttpResponse("Authentication required", status=401)

    # Use core business logic - permissions enforced via GraphQL queries
    all_sites = _export_single_site(site_id, request)
    return _export_sites_response(all_sites, format, site_name)


def user_owned_sites_export_by_id(request, user_id, user_name, format):
    """Export all sites owned by a specific user (not in any project) using user ID (authenticated, enforces permissions)."""
    if not request.user.is_authenticated:
        return HttpResponse("Authentication required", status=401)

    # Use core business logic - permissions enforced via GraphQL queries
    all_sites = _export_user_owned_sites(user_id, request)
    return _export_sites_response(all_sites, format, f"{user_name}_owned_sites")


def user_all_sites_export_by_id(request, user_id, user_name, format):
    """Export all sites owned by user plus all sites in projects where user is a member using user ID (authenticated, enforces permissions)."""
    if not request.user.is_authenticated:
        return HttpResponse("Authentication required", status=401)

    # Use core business logic - permissions enforced via GraphQL queries
    all_sites = _export_user_all_sites(user_id, request)
    return _export_sites_response(all_sites, format, f"{user_name}_and_projects")


# HTML landing pages for export links


def project_export_page(request, project_token, project_name):
    """Return HTML page with download links for project export."""
    # Check if token is valid
    export_token = _resolve_export_token(project_token)
    if export_token is None:
        return invalid_token_page()

    csv_url = f"/export/token/project/{project_token}/{project_name}.csv"
    json_url = f"/export/token/project/{project_token}/{project_name}.json"
    return export_page_html(project_name, "project", csv_url, json_url, request)


def site_export_page(request, site_token, site_name):
    """Return HTML page with download links for site export."""
    # Check if token is valid
    export_token = _resolve_export_token(site_token)
    if export_token is None:
        return invalid_token_page()

    csv_url = f"/export/token/site/{site_token}/{site_name}.csv"
    json_url = f"/export/token/site/{site_token}/{site_name}.json"
    return export_page_html(site_name, "site", csv_url, json_url, request)


def user_owned_sites_export_page(request, user_token, user_name):
    """Return HTML page with download links for user owned sites export."""
    # Check if token is valid
    export_token = _resolve_export_token(user_token)
    if export_token is None:
        return invalid_token_page()

    csv_url = f"/export/token/user_owned/{user_token}/{user_name}.csv"
    json_url = f"/export/token/user_owned/{user_token}/{user_name}.json"
    return export_page_html(user_name, "user_owned", csv_url, json_url, request)


def user_all_sites_export_page(request, user_token, user_name):
    """Return HTML page with download links for user all sites export."""
    # Check if token is valid
    export_token = _resolve_export_token(user_token)
    if export_token is None:
        return invalid_token_page()

    csv_url = f"/export/token/user_all/{user_token}/{user_name}.csv"
    json_url = f"/export/token/user_all/{user_token}/{user_name}.json"
    return export_page_html(user_name, "user_all", csv_url, json_url, request)
