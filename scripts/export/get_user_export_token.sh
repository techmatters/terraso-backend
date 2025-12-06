#!/bin/bash
set -e

# =============================================================================
# Get/Create User Export Token
# =============================================================================
# Creates an export token for a user and displays the shareable URLs.
#
# Usage:
#   ./scripts/export/get_user_export_token.sh <user-email>
#
# Arguments:
#   user-email   Email address of the user
#
# Options:
#   -h, --help   Show this help message
#
# Examples:
#   ./scripts/export/get_user_export_token.sh user@example.com
# =============================================================================

show_help() {
    head -n 18 "$0" | tail -n 16 | sed 's/^# //' | sed 's/^#//'
    exit 0
}

# Parse arguments
if [ $# -eq 0 ]; then
    show_help
fi

case $1 in
    -h|--help)
        show_help
        ;;
esac

USER_EMAIL="$1"

# Check for docker
if ! command -v docker &> /dev/null; then
    echo "Error: docker command not found"
    exit 1
fi

# Find git root and change to it
GIT_ROOT=$(git rev-parse --show-toplevel)
pushd "$GIT_ROOT" > /dev/null

cleanup() {
    popd > /dev/null 2>&1 || true
}
trap cleanup EXIT

# Docker compose files
COMPOSE_FILES="-f docker-compose.base.yml -f docker-compose.dev.yml"

echo "=========================================="
echo "Get/Create User Export Token"
echo "=========================================="
echo "Email: $USER_EMAIL"
echo ""

# Check if web container is running
if ! docker compose $COMPOSE_FILES ps web 2>/dev/null | grep -q "Up"; then
    echo "Error: Backend container is not running"
    echo ""
    echo "Please start the backend first with:"
    echo "  make run"
    echo ""
    exit 1
fi

echo "Backend container is running"
echo ""

# Run Django shell command in existing container
docker compose $COMPOSE_FILES exec -T web python terraso_backend/manage.py shell <<EOF
from apps.core.models import User
from apps.export.models import ExportToken

user_email = '$USER_EMAIL'

try:
    # Find user by email
    user = User.objects.get(email=user_email)
    print(f"Found user: {user.email}")
    print(f"  User ID: {user.id}")
    print("")

    # Get or create export token
    token_obj, created = ExportToken.get_or_create_token(
        resource_type='USER',
        resource_id=str(user.id),
        user_id=str(user.id)
    )

    if created:
        print(f"Created new export token")
    else:
        print(f"Token already exists")

    print(f"  Token: {token_obj.token}")
    print("")

    # Generate export URLs
    username = user_email.split('@')[0].replace('.', '_')

    print("My Sites (owned by me):")
    print(f"    /export/token/user_owned/{token_obj.token}/{username}_my_sites.html")
    print("")
    print("All Sites (owned + shared with me):")
    print(f"    /export/token/user_all/{token_obj.token}/{username}_all_sites.html")
    print("")
    print("Note: Prepend http://localhost:8000 for local dev")

except User.DoesNotExist:
    print(f"Error: User '{user_email}' not found")
    exit(1)
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

EOF

echo ""
echo "=========================================="
