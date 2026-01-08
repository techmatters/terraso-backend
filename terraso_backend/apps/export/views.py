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

from urllib.parse import quote, unquote

from django.contrib.auth import get_user_model
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse

from .fetch_data import fetch_all_notes_for_site, fetch_site_data, fetch_soil_id
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


def _get_resource_name(export_token):
    """
    Look up the actual name of the resource from the database.
    Returns the resource name for display/filename purposes.
    """
    from apps.project_management.models import Project, Site

    if export_token.resource_type == "PROJECT":
        try:
            project = Project.objects.get(id=export_token.resource_id)
            return project.name
        except Project.DoesNotExist:
            return None
    elif export_token.resource_type == "SITE":
        try:
            site = Site.objects.get(id=export_token.resource_id)
            return site.name
        except Site.DoesNotExist:
            return None
    elif export_token.resource_type == "USER":
        User = get_user_model()
        try:
            user = User.objects.get(id=export_token.resource_id)
            full_name = f"{user.first_name} {user.last_name}".strip()
            return full_name or user.email
        except User.DoesNotExist:
            return None
    return None


def _inject_user_ratings_into_matches(soil_id_data, user_ratings):
    """
    Inject user ratings into soil matches based on soil series name.

    Args:
        soil_id_data: The soil_id response data containing soilMatches
        user_ratings: List of {soilMatchId, rating} from soilMetadata.userRatings

    The soilMatchId corresponds to match.soilInfo.soilSeries.name.
    If a match has a corresponding rating, adds "userRating" field.
    If no rating exists for a match, the field is omitted.
    """
    if not user_ratings:
        return

    # Build lookup: {"Catden": "SELECTED", "Hollis": "REJECTED", ...}
    ratings_by_name = {r["soilMatchId"]: r["rating"] for r in user_ratings}

    # Navigate to matches array
    matches = soil_id_data.get("soilId", {}).get("soilMatches", {}).get("matches", [])

    for match in matches:
        series_name = match.get("soilInfo", {}).get("soilSeries", {}).get("name")
        if series_name and series_name in ratings_by_name:
            match["userRating"] = ratings_by_name[series_name]


def _process_sites(site_ids, request, output_format="json"):
    """
    Process a set of site IDs into full site data.
    Returns a sorted list of transformed sites with soil_id data.

    Args:
        site_ids: Set of site UUIDs to process
        request: Django request object
        output_format: "raw", "json", or "csv" - determines processing strategy
    """
    all_sites = []
    for site_id in site_ids:
        site_data = fetch_site_data(site_id, request)

        if output_format == "raw":
            # Return GraphQL data with minimal processing (for testing/debugging)
            # Include notes and soil_id data that would normally be fetched separately
            # Keep soilMetadata in raw output, don't inject userRating into matches
            site_data["notes"] = fetch_all_notes_for_site(site_id, request)
            site_data["soil_id"] = fetch_soil_id(site_data, request)
            all_sites.append(site_data)
        else:
            # Full transformation for CSV/JSON export
            # Fetch soil_id BEFORE transformation since it needs original enum codes
            soil_id_data = fetch_soil_id(site_data, request)
            # Inject user ratings into soil matches (ratings are keyed by soil series name)
            user_ratings = site_data.get("soilMetadata", {}).get("userRatings", [])
            _inject_user_ratings_into_matches(soil_id_data, user_ratings)
            transformed_site = transform_site_data(site_data, request)
            transformed_site["soil_id"] = soil_id_data
            # Preserve selected soil name for CSV export (needed when no soil matches exist)
            # This allows us to show user's selection even when soil ID API returns no matches
            selected_soil_id = site_data.get("soilMetadata", {}).get("selectedSoilId")
            if selected_soil_id:
                transformed_site["_selectedSoilName"] = selected_soil_id
            # Remove soilMetadata from output - user ratings are now in soil_id matches
            transformed_site.pop("soilMetadata", None)
            all_sites.append(transformed_site)

    # Sort sites by name, then by ID for deterministic ordering when names match
    all_sites.sort(key=lambda site: (site.get("name", ""), site.get("id", "")))
    return all_sites


def _strip_null_values(obj):
    """Recursively remove keys with None/null values and internal-only fields from dicts.

    _selectedSoilName is used during CSV processing but should not appear in JSON output.
    (Note: _colorMunsell is intentionally kept in JSON output as a derived field.)
    """
    # Fields to exclude from JSON output (used internally during processing)
    internal_only_fields = {"_selectedSoilName"}

    if isinstance(obj, dict):
        return {
            k: _strip_null_values(v)
            for k, v in obj.items()
            if v is not None and k not in internal_only_fields
        }
    elif isinstance(obj, list):
        return [_strip_null_values(item) for item in obj]
    return obj


def _make_content_disposition(filename):
    """
    Build Content-Disposition header with both filename and filename* for compatibility.

    - filename*: UTF-8 encoded per RFC 5987/6266 for modern browsers
    - filename: ASCII fallback for older clients (non-ASCII replaced with underscore)

    Note: filename* comes first as some clients give precedence to the first parameter.
    Note: curl -O -J does not support filename* (PR #1995 was never merged), so it uses the
    ASCII fallback filename.
    """
    # ASCII-safe fallback: replace non-ASCII characters with underscore
    ascii_filename = filename.encode("ascii", "replace").decode("ascii").replace("?", "_")
    # RFC 5987 format: charset'language'encoded_value (language is optional, hence empty)
    encoded = quote(filename)
    return f"attachment; filename*=UTF-8''{encoded}; filename=\"{ascii_filename}\""


def _get_output_format(request, url_format):
    """
    Determine output format from request and URL.

    Args:
        request: Django request with optional ?format=raw query param
        url_format: Format from URL path ("json" or "csv")

    Returns:
        "raw", "json", or "csv", or None if invalid (raw + csv)
    """
    if request.GET.get("format") == "raw":
        if url_format != "json":
            return None  # Invalid: raw only works with JSON
        return "raw"
    return url_format


def _validate_output_format(output_format):
    """Return error response if output_format is invalid, else None."""
    if output_format is None:
        return HttpResponseBadRequest("Raw format only supports JSON output")
    if output_format not in ["csv", "json", "raw"]:
        return HttpResponseBadRequest(f"Unsupported format: {output_format}")
    return None


def _export_sites_response(all_sites, output_format, filename):
    """Helper function to generate export response for a list of sites.

    Args:
        all_sites: List of site data dicts
        output_format: "raw", "json", or "csv" (must be validated by caller)
        filename: Base filename for Content-Disposition header
    """
    # Determine file format (raw uses json file extension)
    format = "json" if output_format == "raw" else output_format

    # Decode URL-encoded characters in filename (e.g., %20 -> space)
    decoded_filename = unquote(filename)
    full_filename = f"{decoded_filename}.{format}"

    if format == "json":
        cleaned_sites = _strip_null_values(all_sites)
        response = JsonResponse({"sites": cleaned_sites})
        response["Content-Disposition"] = _make_content_disposition(full_filename)
        return response

    response = HttpResponse(sites_to_csv(all_sites), content_type="text/csv")
    response["Content-Disposition"] = _make_content_disposition(full_filename)
    return response


# Core business logic functions (shared by token-based and ID-based exports)


def _export_project_sites(project_id, request, output_format="json"):
    """
    Core logic: Fetch and process all sites in a project.
    Returns sorted list of transformed site data.
    """
    site_ids = fetch_all_sites(project_id, request)
    return _process_sites(site_ids, request, output_format=output_format)


def _export_single_site(site_id, request, output_format="json"):
    """
    Core logic: Fetch and process a single site.
    Returns sorted list of transformed site data (single item).
    """
    site_ids = {site_id}
    return _process_sites(site_ids, request, output_format=output_format)


def _export_user_owned_sites(user_id, request, output_format="json"):
    """
    Core logic: Fetch and process user's unaffiliated sites only.
    Returns sorted list of transformed site data.
    """
    site_ids = fetch_user_owned_sites(user_id, request)
    return _process_sites(site_ids, request, output_format=output_format)


def _export_user_all_sites(user_id, request, output_format="json"):
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

    return _process_sites(site_ids, request, output_format=output_format)


def project_export(request, project_token, project_name, format):
    """Export all sites in a project using export token (public access, no auth required)."""
    export_token = _resolve_export_token(project_token)
    if export_token is None:
        return invalid_token_page()
    if export_token.resource_type != "PROJECT":
        return HttpResponseBadRequest("Invalid token type for project export")

    output_format = _get_output_format(request, format)
    if error := _validate_output_format(output_format):
        return error

    _setup_token_user(request, export_token)
    filename = _get_resource_name(export_token) or unquote(project_name)
    all_sites = _export_project_sites(export_token.resource_id, request, output_format)
    return _export_sites_response(all_sites, output_format, filename)


def site_export(request, site_token, site_name, format):
    """Export a single site using export token (public access, no auth required)."""
    export_token = _resolve_export_token(site_token)
    if export_token is None:
        return invalid_token_page()
    if export_token.resource_type != "SITE":
        return HttpResponseBadRequest("Invalid token type for site export")

    output_format = _get_output_format(request, format)
    if error := _validate_output_format(output_format):
        return error

    _setup_token_user(request, export_token)
    filename = _get_resource_name(export_token) or unquote(site_name)
    all_sites = _export_single_site(export_token.resource_id, request, output_format)
    return _export_sites_response(all_sites, output_format, filename)


def user_owned_sites_export(request, user_token, user_name, format):
    """Export all sites owned by a specific user (not in any project) using export token (public access, no auth required)."""
    export_token = _resolve_export_token(user_token)
    if export_token is None:
        return invalid_token_page()
    if export_token.resource_type != "USER":
        return HttpResponseBadRequest("Invalid token type for user export")

    output_format = _get_output_format(request, format)
    if error := _validate_output_format(output_format):
        return error

    _setup_token_user(request, export_token)
    display_name = _get_resource_name(export_token) or unquote(user_name)
    all_sites = _export_user_owned_sites(export_token.resource_id, request, output_format)
    return _export_sites_response(all_sites, output_format, f"{display_name}_owned_sites")


def user_all_sites_export(request, user_token, user_name, format):
    """Export all sites owned by user plus all sites in projects where user is a member using export token (public access, no auth required)."""
    export_token = _resolve_export_token(user_token)
    if export_token is None:
        return invalid_token_page()
    if export_token.resource_type != "USER":
        return HttpResponseBadRequest("Invalid token type for user export")

    output_format = _get_output_format(request, format)
    if error := _validate_output_format(output_format):
        return error

    _setup_token_user(request, export_token)
    display_name = _get_resource_name(export_token) or unquote(user_name)
    all_sites = _export_user_all_sites(export_token.resource_id, request, output_format)
    return _export_sites_response(all_sites, output_format, f"{display_name}_and_projects")


# ID-based exports (authenticated, enforce permissions)


def project_export_by_id(request, project_id, project_name, format):
    """Export all sites in a project using project ID (authenticated, enforces permissions)."""
    if not request.user.is_authenticated:
        return HttpResponse("Authentication required", status=401)

    output_format = _get_output_format(request, format)
    if error := _validate_output_format(output_format):
        return error

    from apps.project_management.models import Project

    try:
        project = Project.objects.get(id=project_id)
        filename = project.name
    except Project.DoesNotExist:
        filename = unquote(project_name)

    all_sites = _export_project_sites(project_id, request, output_format)
    return _export_sites_response(all_sites, output_format, filename)


def site_export_by_id(request, site_id, site_name, format):
    """Export a single site using site ID (authenticated, enforces permissions)."""
    if not request.user.is_authenticated:
        return HttpResponse("Authentication required", status=401)

    output_format = _get_output_format(request, format)
    if error := _validate_output_format(output_format):
        return error

    from apps.project_management.models import Site

    try:
        site = Site.objects.get(id=site_id)
        filename = site.name
    except Site.DoesNotExist:
        filename = unquote(site_name)

    all_sites = _export_single_site(site_id, request, output_format)
    return _export_sites_response(all_sites, output_format, filename)


def user_owned_sites_export_by_id(request, user_id, user_name, format):
    """Export all sites owned by a specific user (not in any project) using user ID (authenticated, enforces permissions)."""
    if not request.user.is_authenticated:
        return HttpResponse("Authentication required", status=401)

    output_format = _get_output_format(request, format)
    if error := _validate_output_format(output_format):
        return error

    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
        full_name = f"{user.first_name} {user.last_name}".strip()
        display_name = full_name or user.email
    except User.DoesNotExist:
        display_name = unquote(user_name)

    all_sites = _export_user_owned_sites(user_id, request, output_format)
    return _export_sites_response(all_sites, output_format, f"{display_name}_owned_sites")


def user_all_sites_export_by_id(request, user_id, user_name, format):
    """Export all sites owned by user plus all sites in projects where user is a member using user ID (authenticated, enforces permissions)."""
    if not request.user.is_authenticated:
        return HttpResponse("Authentication required", status=401)

    output_format = _get_output_format(request, format)
    if error := _validate_output_format(output_format):
        return error

    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
        full_name = f"{user.first_name} {user.last_name}".strip()
        display_name = full_name or user.email
    except User.DoesNotExist:
        display_name = unquote(user_name)

    all_sites = _export_user_all_sites(user_id, request, output_format)
    return _export_sites_response(all_sites, output_format, f"{display_name}_and_projects")


# HTML landing pages for export links


def project_export_page(request, project_token, project_name):
    """Return HTML page with download links for project export."""
    # Check if token is valid
    export_token = _resolve_export_token(project_token)
    if export_token is None:
        return invalid_token_page()

    # Use actual project name from database for display, URL name for links
    display_name = _get_resource_name(export_token) or unquote(project_name)
    csv_url = f"/export/token/project/{project_token}/{project_name}.csv"
    json_url = f"/export/token/project/{project_token}/{project_name}.json"
    return export_page_html(display_name, "project", csv_url, json_url, request)


def site_export_page(request, site_token, site_name):
    """Return HTML page with download links for site export."""
    # Check if token is valid
    export_token = _resolve_export_token(site_token)
    if export_token is None:
        return invalid_token_page()

    # Use actual site name from database for display, URL name for links
    display_name = _get_resource_name(export_token) or unquote(site_name)
    csv_url = f"/export/token/site/{site_token}/{site_name}.csv"
    json_url = f"/export/token/site/{site_token}/{site_name}.json"
    return export_page_html(display_name, "site", csv_url, json_url, request)


def user_owned_sites_export_page(request, user_token, user_name):
    """Return HTML page with download links for user owned sites export."""
    # Check if token is valid
    export_token = _resolve_export_token(user_token)
    if export_token is None:
        return invalid_token_page()

    # Use actual user name from database for display, URL name for links
    display_name = _get_resource_name(export_token) or unquote(user_name)
    csv_url = f"/export/token/user_owned/{user_token}/{user_name}.csv"
    json_url = f"/export/token/user_owned/{user_token}/{user_name}.json"
    return export_page_html(display_name, "user_owned", csv_url, json_url, request)


def user_all_sites_export_page(request, user_token, user_name):
    """Return HTML page with download links for user all sites export."""
    # Check if token is valid
    export_token = _resolve_export_token(user_token)
    if export_token is None:
        return invalid_token_page()

    # Use actual user name from database for display, URL name for links
    display_name = _get_resource_name(export_token) or unquote(user_name)
    csv_url = f"/export/token/user_all/{user_token}/{user_name}.csv"
    json_url = f"/export/token/user_all/{user_token}/{user_name}.json"
    return export_page_html(display_name, "user_all", csv_url, json_url, request)
