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

"""Server-side point-elevation lookup for the soil-ID ranking.

Elevation is normally supplied by the client (it fetches and stores one per
site) and passed through the soil-ID query. This module is the *fallback* for
when the client didn't send one — e.g. a not-yet-updated app or a temporary map
location — so the US Site score can still be computed.

Source is Mapbox Terrain-RGB: in the US it's built from USGS 3DEP, and it's
served from a CDN (unlike the flaky National Map EPQS endpoint). Failures are
reported to Sentry so we can watch how often the fallback breaks. When it
returns None, the caller ranks without the elevation feature.
"""

import io
import math

import requests
import sentry_sdk
import structlog
from django.conf import settings

logger = structlog.get_logger(__name__)

_TERRAIN_TILESET = "mapbox.terrain-rgb"
_TERRAIN_ZOOM = 14

# Successful elevations only, keyed by rounded (lat, lon). Failures aren't cached
# so a transient error doesn't pin a coordinate to "no elevation" for the life of
# the process. A stray duplicate fetch under gthread workers is harmless.
_elev_cache = {}


def _lonlat_to_tile(longitude, latitude, zoom):
    """Fractional slippy-map tile coordinates (Web Mercator) for a lon/lat."""
    n = 2**zoom
    xf = (longitude + 180.0) / 360.0 * n
    yf = (1.0 - math.asinh(math.tan(math.radians(latitude))) / math.pi) / 2.0 * n
    return xf, yf


def mapbox_elevation(latitude, longitude):
    """Point elevation in meters from Mapbox Terrain-RGB, or None on failure.

    Fetches the DEM tile containing the point, decodes the pixel with Mapbox's
    Terrain-RGB height encoding, and caches successful results by rounded
    coordinates. Returns None (and reports to Sentry) if no token is configured
    or the tile can't be fetched/decoded.
    """
    token = settings.MAPBOX_ACCESS_TOKEN
    if not token:
        return None

    key = (round(latitude, 5), round(longitude, 5))
    if key in _elev_cache:
        return _elev_cache[key]

    from PIL import Image

    xf, yf = _lonlat_to_tile(longitude, latitude, _TERRAIN_ZOOM)
    tx, ty = int(xf), int(yf)
    url = f"https://api.mapbox.com/v4/{_TERRAIN_TILESET}/{_TERRAIN_ZOOM}/{tx}/{ty}.pngraw"

    last_error = None
    for attempt in range(2):
        try:
            response = requests.get(url, params={"access_token": token}, timeout=5)
            response.raise_for_status()
            image = Image.open(io.BytesIO(response.content)).convert("RGB")
            px = min(image.width - 1, int((xf - tx) * image.width))
            py = min(image.height - 1, int((yf - ty) * image.height))
            r, g, b = image.getpixel((px, py))
            # Mapbox Terrain-RGB height encoding (meters).
            elevation = -10000.0 + (r * 65536 + g * 256 + b) * 0.1
            _elev_cache[key] = elevation
            return elevation
        except Exception as error:  # network or tile-decode error
            last_error = error
            logger.warning("mapbox_elevation_attempt_failed", attempt=attempt + 1, error=str(error))

    # Exhausted retries — surface it. capture_message is a no-op when Sentry
    # isn't initialised (e.g. no DSN, or under tests), so this is always safe.
    logger.error(
        "mapbox_elevation_failed",
        latitude=latitude,
        longitude=longitude,
        error=str(last_error),
    )
    sentry_sdk.capture_message(
        f"Mapbox elevation lookup failed at ({latitude}, {longitude}): {last_error}",
        level="error",
    )
    return None
