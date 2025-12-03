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
from .models import ExportToken
from .transformers import transform_site_data


def _invalid_token_page():
    """Generate HTML page for invalid/expired export token."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Invalid Export Link</title>

        <!-- Material Icons -->
        <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">

        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                max-width: 600px;
                margin: 50px auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                background-color: white;
                border-radius: 8px;
                padding: 40px;
                text-align: center;
            }
            .logo {
                width: 120px;
                height: 120px;
                margin: 0 auto 20px;
                display: block;
            }
            .error-icon {
                font-size: 64px;
                color: #dc3545;
                margin: 20px 0;
                display: block;
            }
            h1 {
                color: #333;
                margin: 20px 0;
                font-size: 24px;
            }
            p {
                color: #666;
                line-height: 1.6;
                margin: 15px 0;
            }
            .info-box {
                background-color: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 15px;
                margin: 20px 0;
                text-align: left;
            }
            .info-box strong {
                color: #856404;
            }
            .material-icons {
                vertical-align: middle;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <img src="/static/export/landpks-round.png" alt="LandPKS Logo" class="logo">
            <span class="material-icons error-icon">link_off</span>
            <h1>Export Link No Longer Valid</h1>
            <p>This export link has been reset or expired and is no longer valid.</p>

            <div class="info-box">
                <strong>To get a new export link:</strong>
                <ol style="margin: 10px 0; padding-left: 20px;">
                    <li>Open the LandPKS mobile app</li>
                    <li>Navigate to your project or site</li>
                    <li>Generate a new export link</li>
                </ol>
            </div>

            <p style="font-size: 14px; color: #999; margin-top: 30px;">
                Export links can be reset at any time from the mobile app for security purposes.
            </p>
        </div>
    </body>
    </html>
    """
    return HttpResponse(html_content, content_type="text/html", status=404)


def _resolve_export_token(token):
    """
    Resolve export token to (resource_type, resource_id).
    Returns invalid token page if token not found.
    """
    try:
        export_token = ExportToken.objects.get(token=token)
        return export_token.resource_type, export_token.resource_id
    except ExportToken.DoesNotExist:
        return None, None


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
        # Fetch soil_id BEFORE transformation since it needs original enum codes
        soil_id_data = fetch_soil_id(site_data, request)
        transformed_site = transform_site_data(site_data, request)
        transformed_site["soil_id"] = soil_id_data
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
    _setup_system_export_user(request)

    # Resolve token to actual project ID
    resource_type, project_id = _resolve_export_token(project_token)
    if resource_type is None:
        return _invalid_token_page()
    if resource_type != "PROJECT":
        return HttpResponseBadRequest("Invalid token type for project export")

    # Use core business logic
    all_sites = _export_project_sites(project_id, request)
    return _export_sites_response(all_sites, format, project_name)


def site_export(request, site_token, site_name, format):
    """Export a single site using export token (public access, no auth required)."""
    _setup_system_export_user(request)

    # Resolve token to actual site ID
    resource_type, site_id = _resolve_export_token(site_token)
    if resource_type is None:
        return _invalid_token_page()
    if resource_type != "SITE":
        return HttpResponseBadRequest("Invalid token type for site export")

    # Use core business logic
    all_sites = _export_single_site(site_id, request)
    return _export_sites_response(all_sites, format, site_name)


def user_owned_sites_export(request, user_token, user_name, format):
    """Export all sites owned by a specific user (not in any project) using export token (public access, no auth required)."""
    _setup_system_export_user(request)

    # Resolve token to actual user ID
    resource_type, user_id = _resolve_export_token(user_token)
    if resource_type is None:
        return _invalid_token_page()
    if resource_type != "USER":
        return HttpResponseBadRequest("Invalid token type for user export")

    # Use core business logic
    all_sites = _export_user_owned_sites(user_id, request)
    return _export_sites_response(all_sites, format, f"{user_name}_owned_sites")


def user_all_sites_export(request, user_token, user_name, format):
    """Export all sites owned by user plus all sites in projects where user is a member using export token (public access, no auth required)."""
    _setup_system_export_user(request)

    # Resolve token to actual user ID
    resource_type, user_id = _resolve_export_token(user_token)
    if resource_type is None:
        return _invalid_token_page()
    if resource_type != "USER":
        return HttpResponseBadRequest("Invalid token type for user export")

    # Use core business logic
    all_sites = _export_user_all_sites(user_id, request)
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


def _export_page_html(name, resource_type, csv_url, json_url, request=None):
    """
    Generate HTML page for export with download links.

    Args:
        name: Display name for the export
        resource_type: Type of resource (project, site, user_all, user_owned)
        csv_url: URL for CSV download
        json_url: URL for JSON download
        request: Django request object (optional, for building absolute URLs)
    """
    resource_type_labels = {
        "project": "Project Sites",
        "site": "Single Site",
        "user_all": "All User's Sites (Projects + Unaffiliated)",
        "user_owned": "Owned Sites Only",
    }

    type_label = resource_type_labels.get(resource_type, "Sites")

    # Build absolute URLs for OpenGraph metadata
    if request:
        image_url = request.build_absolute_uri("/static/export/landpks-round.png")
        page_url = request.build_absolute_uri()
    else:
        image_url = "/static/export/landpks-round.png"
        page_url = ""

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Export Download - {name}</title>

        <!-- Material Icons -->
        <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">

        <!-- OpenGraph metadata for link previews -->
        <meta property="og:title" content="LandPKS Export: {name}" />
        <meta property="og:description" content="{type_label} - Download your LandPKS data export in CSV or JSON format" />
        <meta property="og:type" content="website" />
        <meta property="og:url" content="{page_url}" />
        <meta property="og:site_name" content="Terraso LandPKS" />
        <meta property="og:locale" content="en_US" />
        <meta property="og:image" content="{image_url}" />
        <meta property="og:image:width" content="1024" />
        <meta property="og:image:height" content="1024" />
        <meta property="og:image:alt" content="LandPKS Logo - Landscape and soil data platform" />

        <!-- Twitter Card metadata -->
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="LandPKS Export: {name}" />
        <meta name="twitter:description" content="{type_label} - Download your LandPKS data export in CSV or JSON format" />
        <meta name="twitter:image" content="{image_url}" />
        <meta name="twitter:image:alt" content="LandPKS Logo - Landscape and soil data platform" />

        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                max-width: 600px;
                margin: 50px auto;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .container {{
                background-color: white;
                border-radius: 8px;
                padding: 40px;
                text-align: center;
            }}
            .logo {{
                width: 120px;
                height: 120px;
                margin: 0 auto 20px;
            }}
            h1 {{
                color: #333;
                margin-top: 0;
                font-size: 24px;
            }}
            p {{
                color: #666;
                line-height: 1.6;
            }}
            .download-row {{
                display: flex;
                align-items: center;
                gap: 10px;
                margin: 10px 0;
            }}
            .download-link {{
                flex: 1;
                background-color: #028843;
                color: white;
                padding: 0 24px;
                text-decoration: none;
                border-radius: 4px;
                font-weight: 500;
                text-align: center;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 6px;
                height: 48px;
            }}
            .download-link:hover {{
                background-color: #026E38;
            }}
            .copy-button {{
                display: inline-flex;
                align-items: center;
                justify-content: center;
                gap: 6px;
                background-color: #6c757d;
                color: white;
                padding: 0 16px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-weight: 500;
                font-size: 14px;
                white-space: nowrap;
                width: 135px;
                height: 48px;
            }}
            .copy-button:hover {{
                background-color: #5a6268;
            }}
            .copy-button.copied {{
                background-color: #5a6268;
            }}
            .info {{
                background-color: #f8f9fa;
                padding: 15px;
                border-radius: 4px;
                margin-top: 20px;
                text-align: left;
            }}
            .info-label {{
                font-weight: 600;
                color: #333;
            }}
            .info-value {{
                color: #666;
            }}
            .download-section {{
                margin-top: 30px;
            }}
            .material-icons {{
                font-size: 18px;
                vertical-align: middle;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <img src="/static/export/landpks-round.png" alt="LandPKS Logo" class="logo">
            <h1>LandPKS Soil ID Data Export</h1>
            <p>Exports will always contain up-to-date data. Export links will be valid until reset in the mobile app.</p>

            <div class="info">
                <div style="margin-bottom: 10px;">
                    <span class="info-label">Export name:</span>
                    <span class="info-value">{name}</span>
                </div>
                <div>
                    <span class="info-label">Export type:</span>
                    <span class="info-value">{type_label}</span>
                </div>
            </div>

            <div class="download-section">
                <div class="download-row">
                    <a href="{csv_url}" class="download-link" download>
                        <span class="material-icons">file_download</span>
                        Download CSV
                    </a>
                    <button class="copy-button" onclick="copyLink('{csv_url}', this)">
                        <span class="material-icons">share</span>
                        <span class="copy-text">Copy Link</span>
                    </button>
                </div>
                <div class="download-row">
                    <a href="{json_url}" class="download-link" download>
                        <span class="material-icons">file_download</span>
                        Download JSON
                    </a>
                    <button class="copy-button" onclick="copyLink('{json_url}', this)">
                        <span class="material-icons">share</span>
                        <span class="copy-text">Copy Link</span>
                    </button>
                </div>
            </div>

        </div>

        <script>
            function copyLink(relativeUrl, button) {{
                // Build absolute URL from relative path
                const baseUrl = window.location.origin;
                const absoluteUrl = baseUrl + relativeUrl;

                // Try modern clipboard API first, fallback to older method
                if (navigator.clipboard && navigator.clipboard.writeText) {{
                    navigator.clipboard.writeText(absoluteUrl).then(() => {{
                        showCopiedFeedback(button);
                    }}).catch(err => {{
                        console.log('Clipboard API failed, using fallback:', err);
                        fallbackCopy(absoluteUrl, button);
                    }});
                }} else {{
                    fallbackCopy(absoluteUrl, button);
                }}
            }}

            function fallbackCopy(text, button) {{
                // Fallback method that works without HTTPS
                const textArea = document.createElement('textarea');
                textArea.value = text;
                textArea.style.position = 'fixed';
                textArea.style.left = '-999999px';
                textArea.style.top = '-999999px';
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();

                try {{
                    const successful = document.execCommand('copy');
                    if (successful) {{
                        showCopiedFeedback(button);
                    }} else {{
                        alert('Failed to copy link');
                    }}
                }} catch (err) {{
                    console.error('Fallback copy failed:', err);
                    alert('Failed to copy link');
                }} finally {{
                    document.body.removeChild(textArea);
                }}
            }}

            function showCopiedFeedback(button) {{
                const textSpan = button.querySelector('.copy-text');
                button.classList.add('copied');
                textSpan.textContent = 'Copied!';
                setTimeout(() => {{
                    button.classList.remove('copied');
                    textSpan.textContent = 'Copy Link';
                }}, 2000);
            }}
        </script>
    </body>
    </html>
    """

    return HttpResponse(html_content, content_type="text/html")


def project_export_page(request, project_token, project_name):
    """Return HTML page with download links for project export."""
    # Check if token is valid
    resource_type, _ = _resolve_export_token(project_token)
    if resource_type is None:
        return _invalid_token_page()

    csv_url = f"/export/token/project/{project_token}/{project_name}.csv"
    json_url = f"/export/token/project/{project_token}/{project_name}.json"
    return _export_page_html(project_name, "project", csv_url, json_url, request)


def site_export_page(request, site_token, site_name):
    """Return HTML page with download links for site export."""
    # Check if token is valid
    resource_type, _ = _resolve_export_token(site_token)
    if resource_type is None:
        return _invalid_token_page()

    csv_url = f"/export/token/site/{site_token}/{site_name}.csv"
    json_url = f"/export/token/site/{site_token}/{site_name}.json"
    return _export_page_html(site_name, "site", csv_url, json_url, request)


def user_owned_sites_export_page(request, user_token, user_name):
    """Return HTML page with download links for user owned sites export."""
    # Check if token is valid
    resource_type, _ = _resolve_export_token(user_token)
    if resource_type is None:
        return _invalid_token_page()

    csv_url = f"/export/token/user_owned/{user_token}/{user_name}.csv"
    json_url = f"/export/token/user_owned/{user_token}/{user_name}.json"
    return _export_page_html(user_name, "user_owned", csv_url, json_url, request)


def user_all_sites_export_page(request, user_token, user_name):
    """Return HTML page with download links for user all sites export."""
    # Check if token is valid
    resource_type, _ = _resolve_export_token(user_token)
    if resource_type is None:
        return _invalid_token_page()

    csv_url = f"/export/token/user_all/{user_token}/{user_name}.csv"
    json_url = f"/export/token/user_all/{user_token}/{user_name}.json"
    return _export_page_html(user_name, "user_all", csv_url, json_url, request)
