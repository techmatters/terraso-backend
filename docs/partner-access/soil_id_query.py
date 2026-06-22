#!/usr/bin/env python3
# Copyright © 2026 Technology Matters
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
"""Sample: run a Terraso soil-ID lookup as a partner service account.

What it does
------------
1. Reads the lookup input from ``soil_id_query_params.json``.
2. Reads cached credentials from a tokens file (default
   ``~/secrets/terraso/tokens.json``) and POSTs the ``soilMatches`` GraphQL
   query — requesting every field the ``SoilId`` schema exposes — to
   ``{BASE_URL}/graphql/`` using the cached access token.
3. If the call is rejected because the caller is unauthenticated — the
   ``soilId`` field is gated to authenticated users — it exchanges the
   partner refresh token at ``{BASE_URL}/auth/tokens`` for a fresh access
   token, writes that token back to the tokens file (so the next run reuses
   it), and retries the query once.
4. Prints the full response to stdout (status/progress goes to stderr).

Tokens file
-----------
A small JSON file, kept OUTSIDE this repository, holding the credentials::

    {
      "refresh_token": "<your-long-lived partner refresh token>",
      "access_token":  "<cached; written by this script>"
    }

Seed it once with the ``refresh_token`` you were supplied; the script fills in
/ refreshes ``access_token`` as needed. The original long-lived
``refresh_token`` is preserved — the rotated token the endpoint returns on each
refresh is intentionally ignored.

Configuration (environment variables)
--------------------------------------
- ``TERRASO_API_BASE_URL``  Base URL of the API. Default ``https://api.terraso.org``
                            (override, e.g. ``http://localhost:8000``, for local dev).

The tokens-file path is fixed at ``~/secrets/terraso/tokens.json``.

Security
--------
Token values are never printed, logged, or written into this repository. They
live only in the tokens file (written ``chmod 600``, outside the repo) and in
memory.

Uses only the Python standard library — no pip install required.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REQUEST_FILE = HERE / "soil_id_query_params.json"

BASE_URL = os.environ.get("TERRASO_API_BASE_URL", "https://api.terraso.org").rstrip("/")
GRAPHQL_URL = f"{BASE_URL}/graphql/"
TOKENS_URL = f"{BASE_URL}/auth/tokens"

TOKENS_FILE = Path.home() / "secrets" / "terraso" / "tokens.json"

# Full soilMatches query — every field the SoilId schema currently exposes.
# `soilMatches` returns a union: SoilMatches on success, SoilIdFailure on a
# handled failure (e.g. DATA_UNAVAILABLE), so both are spread inline.
SOIL_ID_QUERY = """
query soilMatches($latitude: Float!, $longitude: Float!, $data: SoilIdInputData!) {
  soilId {
    soilMatches(latitude: $latitude, longitude: $longitude, data: $data) {
      __typename
      ... on SoilMatches {
        dataRegion
        matches {
          dataSource
          distanceToNearestMapUnitM
          locationMatch { score rank }
          dataMatch { score rank }
          combinedMatch { score rank }
          soilInfo {
            soilSeries {
              name
              taxonomySubgroup
              description
              management
              fullDescriptionUrl
            }
            ecologicalSite { name id url }
            landCapabilityClass { capabilityClass subClass }
            soilData {
              slope
              depthDependentData {
                depthInterval { start end }
                texture
                rockFragmentVolume
                munsellColorString
              }
            }
          }
        }
      }
      ... on SoilIdFailure { reason }
    }
  }
}
"""


def _post_json(url, payload, access_token=None):
    """POST a JSON body and return (http_status, parsed_json_body)."""
    data = json.dumps(payload).encode("utf-8")
    # Set an explicit User-Agent: the default "Python-urllib/x.y" is banned by
    # the Cloudflare edge in front of the API (rejected with HTTP 403 "error
    # code: 1010" before the request reaches the backend).
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "terraso-partner-soil-id/1.0",
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"error": body}
    except urllib.error.URLError as exc:
        sys.exit(f"Could not reach {url}: {exc.reason}")


def _is_auth_failure(status, body):
    """True if the response indicates the caller was not authenticated.

    The soilId gate raises a GraphQL error with code ``read_not_allowed``
    (HTTP 200 with an ``errors`` array), but we also treat a 401/403 as an
    auth failure in case a middleware rejects the request earlier.
    """
    if status in (401, 403):
        return True
    for error in body.get("errors") or []:
        message = json.dumps(error)
        if "not_allowed" in message or "AnonymousUser" in message:
            return True
    return False


def _load_tokens():
    """Read the tokens file into a dict; {} if it does not exist yet."""
    if TOKENS_FILE.exists():
        try:
            return json.loads(TOKENS_FILE.read_text())
        except json.JSONDecodeError:
            sys.exit(f"Tokens file {TOKENS_FILE} is not valid JSON.")
    return {}


def _save_tokens(tokens):
    """Persist tokens (owner-only perms), creating parent dirs as needed."""
    TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKENS_FILE.write_text(json.dumps(tokens, indent=2) + "\n")
    try:
        TOKENS_FILE.chmod(0o600)
    except OSError:
        pass  # best-effort on filesystems without POSIX permissions


def _refresh_access_token(refresh_token):
    """Exchange the partner refresh token for a fresh access token."""
    status, body = _post_json(TOKENS_URL, {"refresh_token": refresh_token})
    access_token = body.get("access_token")
    if status != 200 or not access_token:
        # body may contain {"error": "..."}; surface it without any token value.
        sys.exit(f"Token refresh failed (HTTP {status}): {body.get('error', body)}")
    print("Obtained a fresh access token via the partner refresh token.", file=sys.stderr)
    return access_token


def run_query(variables, access_token):
    return _post_json(
        GRAPHQL_URL,
        {"query": SOIL_ID_QUERY, "variables": variables},
        access_token=access_token,
    )


def main():
    variables = json.loads(REQUEST_FILE.read_text())

    tokens = _load_tokens()
    refresh_token = tokens.get("refresh_token")
    access_token = tokens.get("access_token")

    if not refresh_token and not access_token:
        sys.exit(
            f"No credentials found. Create {TOKENS_FILE} containing the partner "
            'refresh token you were supplied:\n'
            '  {"refresh_token": "<your-partner-refresh-token>"}'
        )

    print(f"Querying {GRAPHQL_URL} ...", file=sys.stderr)
    status, body = run_query(variables, access_token)

    if _is_auth_failure(status, body):
        if not refresh_token:
            sys.exit("Access token was rejected and no refresh token is available to renew it.")
        print("Access token missing/expired. Refreshing and retrying once...", file=sys.stderr)
        access_token = _refresh_access_token(refresh_token)
        # Cache the new access token for next time. Keep the original
        # long-lived refresh token rather than the rotated one the endpoint
        # returns, so the file stays a durable partner credential.
        tokens["refresh_token"] = refresh_token
        tokens["access_token"] = access_token
        _save_tokens(tokens)
        print(f"Cached the new access token in {TOKENS_FILE}", file=sys.stderr)
        status, body = run_query(variables, access_token)

    print(json.dumps(body, indent=2))
    print(f"HTTP {status}", file=sys.stderr)

    if body.get("errors"):
        print("GraphQL returned errors (see the output above).", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
