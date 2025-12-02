#!/bin/bash
set -e

# Check if email argument provided
if [ -z "$1" ]; then
    echo "Usage: $0 <user-email>"
    echo ""
    echo "Example:"
    echo "  $0 derek@techmatters.org"
    echo ""
    exit 1
fi

USER_EMAIL="$1"

echo "=========================================="
echo "Get/Create User Export Token"
echo "=========================================="
echo "Email: $USER_EMAIL"
echo ""

# Check if web container is running
if ! docker compose -f docker-compose.dev.yml ps web | grep -q "Up"; then
    echo "✗ ERROR: Backend container is not running"
    echo ""
    echo "Please start the backend first with:"
    echo "  make run"
    echo ""
    exit 1
fi

echo "✓ Backend container is running"
echo ""

# Run Django shell command in existing container
docker compose -f docker-compose.dev.yml exec -T web python terraso_backend/manage.py shell <<EOF
from apps.core.models import User
from apps.export.models import ExportToken

user_email = '$USER_EMAIL'

try:
    # Find user by email
    user = User.objects.get(email=user_email)
    print(f"✓ Found user: {user.email}")
    print(f"  User ID: {user.id}")
    print("")

    # Get or create export token
    token_obj, created = ExportToken.get_or_create_token(
        resource_type='USER',
        resource_id=str(user.id),
        user_id=str(user.id)
    )

    if created:
        print(f"✓ Created new export token")
    else:
        print(f"✓ Token already exists")

    print(f"  Token: {token_obj.token}")
    print("")

    # Generate export URLs
    username = user_email.split('@')[0].replace('.', '_')
    print("Export Link Page (shareable):")
    print(f"  /export/token/user_all/{token_obj.token}/{username}_all_sites.html")
    print("")
    print("Direct Download URLs:")
    print(f"  CSV:  /export/token/user_all/{token_obj.token}/{username}_all_sites.csv")
    print(f"  JSON: /export/token/user_all/{token_obj.token}/{username}_all_sites.json")

except User.DoesNotExist:
    print(f"✗ ERROR: User '{user_email}' not found")
    exit(1)
except Exception as e:
    print(f"✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

EOF

echo ""
echo "=========================================="
