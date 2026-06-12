#!/usr/bin/env bash
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
#
# Sample: run a Terraso soil-ID lookup as a partner service account (bash).
#
# Flow:
#   1. Read credentials from the tokens file (~/secrets/terraso/tokens.json).
#   2. POST the soilMatches query (every field the SoilId schema exposes) to
#      {BASE_URL}/graphql/ using the cached access token.
#   3. If rejected because unauthenticated, exchange the refresh token at
#      {BASE_URL}/auth/tokens for a fresh access token, write it back to the
#      tokens file, and retry once.
#   4. Print the response to stdout (status/progress goes to stderr).
#
# Tokens file (kept OUTSIDE this repo), seeded once with the refresh token you
# were supplied:
#   { "refresh_token": "<your-long-lived partner refresh token>" }
# The script fills in / refreshes "access_token". The original long-lived
# refresh token is preserved (the rotated one from each refresh is ignored).
#
# Token values are never printed, logged, or written into this repository.
#
# Requires: bash, curl, jq.

set -euo pipefail

BASE_URL="${TERRASO_API_BASE_URL:-https://api.terraso.org}"
BASE_URL="${BASE_URL%/}"
GRAPHQL_URL="$BASE_URL/graphql/"
TOKENS_URL="$BASE_URL/auth/tokens"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUEST_FILE="$HERE/soil_id_query_params.json"
TOKENS_FILE="$HOME/secrets/terraso/tokens.json"

# Full soilMatches query — every field the SoilId schema currently exposes.
# soilMatches returns a union: SoilMatches on success, SoilIdFailure on a
# handled failure (e.g. DATA_UNAVAILABLE), so both are spread inline.
read -r -d '' SOIL_ID_QUERY <<'GQL' || true
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
            soilSeries { name taxonomySubgroup description management fullDescriptionUrl }
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
GQL

command -v curl >/dev/null 2>&1 || { echo "curl is required." >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "jq is required." >&2; exit 1; }
[ -f "$REQUEST_FILE" ] || { echo "Missing request file: $REQUEST_FILE" >&2; exit 1; }

if [ ! -f "$TOKENS_FILE" ]; then
  echo "No tokens file at $TOKENS_FILE. Create it with the partner refresh token" >&2
  echo "you were supplied, then re-run:" >&2
  echo '  { "refresh_token": "<your-partner-refresh-token>" }' >&2
  exit 1
fi

REFRESH_TOKEN="$(jq -r '.refresh_token // empty' "$TOKENS_FILE")"
ACCESS_TOKEN="$(jq -r '.access_token // empty' "$TOKENS_FILE")"
if [ -z "$REFRESH_TOKEN" ] && [ -z "$ACCESS_TOKEN" ]; then
  echo "Tokens file $TOKENS_FILE has neither refresh_token nor access_token." >&2
  exit 1
fi

TMP_BODY="$(mktemp)"
TMP_REFRESH="$(mktemp)"
trap 'rm -f "$TMP_BODY" "$TMP_REFRESH"' EXIT

# Request body: combine the query with the variables from the request file.
REQUEST_BODY="$(jq -n --arg q "$SOIL_ID_QUERY" --slurpfile vars "$REQUEST_FILE" \
  '{query: $q, variables: $vars[0]}')"

HTTP_STATUS=""

run_query() {
  local args=(
    -sS -o "$TMP_BODY" -w '%{http_code}'
    -X POST "$GRAPHQL_URL"
    -H 'Content-Type: application/json'
    --data "$REQUEST_BODY"
  )
  if [ -n "$ACCESS_TOKEN" ]; then
    args+=(-H "Authorization: Bearer $ACCESS_TOKEN")
  fi
  HTTP_STATUS="$(curl "${args[@]}")" \
    || { echo "Could not reach $GRAPHQL_URL" >&2; exit 1; }
}

is_auth_failure() {
  # 401/403, or a GraphQL error carrying the soilId gate's not-allowed code.
  if [ "$HTTP_STATUS" = "401" ] || [ "$HTTP_STATUS" = "403" ]; then
    return 0
  fi
  jq -e '(.errors // []) | tostring | test("not_allowed|AnonymousUser")' \
    "$TMP_BODY" >/dev/null 2>&1
}

refresh_access_token() {
  if [ -z "$REFRESH_TOKEN" ]; then
    echo "Access token was rejected and the tokens file has no refresh_token to renew it." >&2
    exit 1
  fi
  local status
  status="$(curl -sS -o "$TMP_REFRESH" -w '%{http_code}' \
    -X POST "$TOKENS_URL" \
    -H 'Content-Type: application/json' \
    --data "$(jq -n --arg rt "$REFRESH_TOKEN" '{refresh_token: $rt}')")" \
    || { echo "Could not reach $TOKENS_URL" >&2; exit 1; }
  if [ "$status" != "200" ]; then
    echo "Token refresh failed (HTTP $status): $(jq -r '.error // "unknown error"' "$TMP_REFRESH" 2>/dev/null)" >&2
    exit 1
  fi
  ACCESS_TOKEN="$(jq -r '.access_token // empty' "$TMP_REFRESH")"
  if [ -z "$ACCESS_TOKEN" ]; then
    echo "Refresh response did not contain an access_token." >&2
    exit 1
  fi
  echo "Obtained a fresh access token via the partner refresh token." >&2
}

save_access_token() {
  # Update only access_token; keep the original (long-lived) refresh token and
  # any other keys. Write via a temp file in the same dir, then chmod 600.
  local dir tmp
  dir="$(dirname "$TOKENS_FILE")"
  mkdir -p "$dir"
  tmp="$(mktemp "$dir/.tokens.XXXXXX")"
  jq --arg at "$ACCESS_TOKEN" '.access_token = $at' "$TOKENS_FILE" >"$tmp"
  mv "$tmp" "$TOKENS_FILE"
  chmod 600 "$TOKENS_FILE"
}

echo "Querying $GRAPHQL_URL ..." >&2
run_query

if is_auth_failure; then
  echo "Access token missing/expired. Refreshing and retrying once..." >&2
  refresh_access_token
  save_access_token
  echo "Cached the new access token in $TOKENS_FILE" >&2
  run_query
fi

jq '.' "$TMP_BODY"
echo "HTTP $HTTP_STATUS" >&2

if jq -e '.errors' "$TMP_BODY" >/dev/null 2>&1; then
  echo "GraphQL returned errors (see the output above)." >&2
  exit 1
fi
