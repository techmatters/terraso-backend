#!/bin/bash
set -euo pipefail

# =============================================================================
# dualserver.sh — run two Terraso API servers at once for staging->prod merge
# testing. web_staging -> terraso_staging DB (:8001), web_prod -> terraso_prod
# DB (:8002). Both share the single local `db` container. See
# docker-compose.dualserver.yml.
#
# Usage:
#   ./dualserver.sh up                 Start db + both servers (detached).
#   ./dualserver.sh down               Stop + remove both servers (db stays up).
#   ./dualserver.sh restart            Restart both servers.
#   ./dualserver.sh ps                 Show status.
#   ./dualserver.sh logs [staging|prod]  Tail logs (both, or one).
#   ./dualserver.sh token <staging|prod> <email>
#                                      Mint a JWT for a user in that DB copy.
#   ./dualserver.sh urls               Print the API endpoints.
#
# Env overrides: STAGING_API_PORT (8001), PROD_API_PORT (8002),
#                TERRASO_ENV_FILE (~/secrets/terraso-backend/.env).
# =============================================================================

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ENV_FILE="${TERRASO_ENV_FILE:-$HOME/secrets/terraso-backend/.env}"
STAGING_API_PORT="${STAGING_API_PORT:-8001}"
PROD_API_PORT="${PROD_API_PORT:-8002}"
export STAGING_API_PORT PROD_API_PORT

DC=(docker compose --env-file "$ENV_FILE"
    -f docker-compose.base.yml -f docker-compose.dev.yml -f docker-compose.dualserver.yml)

print_urls() {
    echo "  staging API -> http://localhost:${STAGING_API_PORT}/graphql   (terraso_staging DB)"
    echo "  prod    API -> http://localhost:${PROD_API_PORT}/graphql   (terraso_prod DB)"
}

cmd="${1:-}"
case "$cmd" in
    up)
        "${DC[@]}" up -d db web_staging web_prod
        echo "Up:"
        print_urls
        ;;
    down)
        # Stop + remove just the two servers; leave the shared db running.
        "${DC[@]}" rm -fs web_staging web_prod
        echo "Stopped web_staging + web_prod (db left running)."
        ;;
    restart)
        "${DC[@]}" restart web_staging web_prod
        print_urls
        ;;
    ps)
        "${DC[@]}" ps
        ;;
    logs)
        case "${2:-}" in
            staging) "${DC[@]}" logs -f --tail=50 web_staging ;;
            prod)    "${DC[@]}" logs -f --tail=50 web_prod ;;
            "")      "${DC[@]}" logs -f --tail=50 web_staging web_prod ;;
            *)       echo "Error: logs arg must be 'staging', 'prod', or empty" >&2; exit 1 ;;
        esac
        ;;
    token)
        env="${2:-}"; email="${3:-}"
        case "$env" in staging|prod) ;; *) echo "Error: token <staging|prod> <email>" >&2; exit 1 ;; esac
        [ -n "$email" ] || { echo "Error: token <staging|prod> <email>" >&2; exit 1; }
        # Mint a JWT for ANY user in the local copy (bypasses the e2e test-user
        # check in `generate_test_token`). Safe: these are disposable local DBs.
        # Email passed via env to avoid shell-quoting the python snippet.
        "${DC[@]}" run --rm --no-deps \
            -e DATABASE_URL="postgres://postgres:postgres@db:5432/terraso_${env}" \
            -e TEST_EMAIL="$email" \
            web python terraso_backend/manage.py shell -c \
            'import os; from apps.core.models import User; from apps.auth.services import JWTService; print("TOKEN:", JWTService().create_test_access_token(User.objects.get(email=os.environ["TEST_EMAIL"])))'
        ;;
    urls)
        print_urls
        ;;
    *)
        grep -E '^#( |$)' "${BASH_SOURCE[0]}" | sed -E 's/^# ?//'
        exit 1
        ;;
esac
