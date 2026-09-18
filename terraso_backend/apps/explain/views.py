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

"""Render a soil-ID explain trace as a self-contained HTML report.

The heavy lifting — turning a scoring trace into HTML — lives in the soil-id
algorithm package (`soil_id.render_explain.render_html`), its natural home. This
view is thin glue: it fetches the site export's `.json?explain=true` payload,
pulls the first site's `soilIdExplanation` trace out of the export envelope
(a terraso-backend concept, so it stays here), and hands it to the renderer.

We reach the export endpoint over plain HTTP rather than calling its views
in-process, on purpose: the only coupling to apps.export is its public URL
contract, so this whole feature can be removed or relocated freely.
"""

import json
import urllib.request
from urllib.parse import urlsplit, urlunsplit

import structlog
from django.http import HttpResponse

logger = structlog.get_logger(__name__)

_FETCH_TIMEOUT_SECONDS = 30


def _export_json_url(request):
    """Reconstruct the sibling export trace URL for this /explain/… request.

    /explain/token/<type>/<token>/<name>.html
        -> /export/token/<type>/<token>/<name>.json?explain=true

    Host comes from the incoming request (honoring Django's ALLOWED_HOSTS), so
    it works across environments without configuration.
    """
    parts = urlsplit(request.build_absolute_uri())
    path = parts.path.replace("/explain/", "/export/", 1)
    if path.endswith(".html"):
        path = f"{path[: -len('.html')]}.json"
    return urlunsplit((parts.scheme, parts.netloc, path, "explain=true", ""))


def _error_page(message, status):
    return HttpResponse(
        f"<!doctype html><meta charset=utf-8><title>Soil ID explanation</title>"
        f"<p style='font:14px -apple-system,sans-serif;margin:40px'>{message}</p>",
        status=status,
        content_type="text/html",
    )


def explain_report(request, resource_type, token, name):
    # The renderer ships with the soil-id algorithm. Import lazily so the backend
    # still boots — and this endpoint degrades to a clear 501 — on soil-id builds
    # that predate it. Bump the soil-id pin to light it up; no code change here.
    try:
        from soil_id.render_explain import render_html
    except ImportError:
        logger.warning("explain_renderer_unavailable", resource_type=resource_type)
        return _error_page(
            "The soil-ID explain renderer is not available in the installed soil-id build.",
            status=501,
        )

    url = _export_json_url(request)
    try:
        with urllib.request.urlopen(url, timeout=_FETCH_TIMEOUT_SECONDS) as resp:
            data = json.load(resp)
    except Exception as error:
        logger.warning("explain_export_fetch_failed", resource_type=resource_type, error=str(error))
        return _error_page("Could not fetch the export data for this report.", status=502)

    sites = data.get("sites") or []
    if not sites:
        return _error_page("This export contains no sites.", status=404)

    # The app (and this report) surface a single site's explanation; a multi-site
    # export renders its first site, matching the render script's behavior.
    trace = sites[0].get("soilIdExplanation")
    if not trace:
        return _error_page(
            "No soil-ID explanation is available for this site "
            "(the export must be requested with ?explain=true).",
            status=404,
        )

    return HttpResponse(render_html(trace), content_type="text/html")
