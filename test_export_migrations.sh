#!/bin/bash

# Test script for export system with fresh production database restore
# This script:
# 1. Restores production database from dump
# 2. Runs all migrations (including export and user_ratings)
# 3. Creates test export tokens for Derek
# 4. Tests all export endpoints

set -e  # Exit on error

echo "========================================="
echo "Export System Migration Test"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Drop and recreate database
echo -e "${YELLOW}Step 1: Dropping existing database...${NC}"
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py shell -c "
from django.db import connection
from django.db.utils import OperationalError

# Close all connections
connection.close()

# Drop all tables except PostGIS system tables
with connection.cursor() as cursor:
    cursor.execute(\"\"\"
        DO \$\$ DECLARE
            r RECORD;
        BEGIN
            FOR r IN (
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename NOT IN ('spatial_ref_sys', 'geography_columns', 'geometry_columns')
            ) LOOP
                EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
            END LOOP;
        END \$\$;
    \"\"\")
    print('All tables dropped (except PostGIS system tables)')
"

# Step 2: Restore from production dump
echo ""
echo -e "${YELLOW}Step 2: Restoring production database from /tmp/g8od_dump.sql...${NC}"
echo "This may take a few minutes..."
cat /tmp/g8od_dump.sql | docker exec -i terraso-backend-db-1 psql -U postgres terraso_backend 2>&1 | tail -5
echo -e "${GREEN}Database restored${NC}"

# Step 3: Check migration state
echo ""
echo -e "${YELLOW}Step 3: Checking migration state...${NC}"
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py showmigrations | grep -E "(core|soil_id|project_management|export)" | tail -20

# Step 4: Run migrations
echo ""
echo -e "${YELLOW}Step 4: Running migrations...${NC}"
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py migrate

# Step 5: Verify system export user was created
echo ""
echo -e "${YELLOW}Step 5: Verifying system export user...${NC}"
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py shell -c "
from apps.core.models import User
try:
    user = User.objects.get(email='system-export@terraso.org')
    print(f'✓ System export user exists: {user.email}')
except User.DoesNotExist:
    print('✗ ERROR: System export user not found!')
    exit(1)
"

# Step 6: Verify user_ratings migration worked
echo ""
echo -e "${YELLOW}Step 6: Verifying user_ratings migration...${NC}"
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py shell -c "
from django.db import connection
with connection.cursor() as cursor:
    # Check if selected_soil_id is gone
    cursor.execute(\"\"\"
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name='soil_id_soilmetadata' AND column_name='selected_soil_id';
    \"\"\")
    old_field = cursor.fetchone()

    # Check if user_ratings exists
    cursor.execute(\"\"\"
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name='soil_id_soilmetadata' AND column_name='user_ratings';
    \"\"\")
    new_field = cursor.fetchone()

    if old_field:
        print('✗ ERROR: Old field selected_soil_id still exists!')
        exit(1)
    elif not new_field:
        print('✗ ERROR: New field user_ratings does not exist!')
        exit(1)
    else:
        print('✓ user_ratings migration successful (selected_soil_id → user_ratings)')
"

# Step 7: Create export tokens for a test user
echo ""
echo -e "${YELLOW}Step 7: Creating export tokens for test user...${NC}"
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py shell -c "
import json
from apps.core.models import User
from apps.project_management.models import Project, Site
from apps.export.models import ExportToken

# Find a user
user = User.objects.filter(
    deleted_at__isnull=True
).exclude(email='system-export@terraso.org').first()

if not user:
    print('ERROR: No users found')
    exit(1)

# Create USER token using the create_token method
try:
    user_token = ExportToken.objects.get(resource_type='USER', resource_id=str(user.id))
except ExportToken.DoesNotExist:
    user_token = ExportToken.create_token('USER', str(user.id))

# Find a project (any project)
project = Project.objects.filter(deleted_at__isnull=True).first()

if not project:
    print('WARNING: No projects found, skipping project token')
    project_token_str = 'NONE'
    project_name = 'N/A'
    project_slug = 'n-a'
else:
    # Create PROJECT token
    try:
        project_token = ExportToken.objects.get(resource_type='PROJECT', resource_id=str(project.id))
    except ExportToken.DoesNotExist:
        project_token = ExportToken.create_token('PROJECT', str(project.id))
    project_token_str = str(project_token.token)
    project_name = project.name
    project_slug = project.slug

# Find a site
site = Site.objects.filter(deleted_at__isnull=True).first()

if not site:
    print('WARNING: No sites found, skipping site token')
    site_token_str = 'NONE'
    site_name = 'N/A'
else:
    # Create SITE token
    try:
        site_token = ExportToken.objects.get(resource_type='SITE', resource_id=str(site.id))
    except ExportToken.DoesNotExist:
        site_token = ExportToken.create_token('SITE', str(site.id))
    site_token_str = str(site_token.token)
    site_name = site.name

# Output as JSON to file
result = {
    'user_token': str(user_token.token),
    'user_email': user.email,
    'project_token': project_token_str,
    'project_name': project_name,
    'project_slug': project_slug,
    'site_token': site_token_str,
    'site_name': site_name
}
with open('/tmp/export_tokens.json', 'w') as f:
    json.dump(result, f)
print('Tokens saved to /tmp/export_tokens.json')
" > /dev/null 2>&1

# Parse the JSON output using jq
USER_TOKEN=$(jq -r '.user_token' /tmp/export_tokens.json)
USER_EMAIL=$(jq -r '.user_email' /tmp/export_tokens.json)
PROJECT_TOKEN=$(jq -r '.project_token' /tmp/export_tokens.json)
PROJECT_NAME=$(jq -r '.project_name' /tmp/export_tokens.json)
PROJECT_SLUG=$(jq -r '.project_slug' /tmp/export_tokens.json)
SITE_TOKEN=$(jq -r '.site_token' /tmp/export_tokens.json)
SITE_NAME=$(jq -r '.site_name' /tmp/export_tokens.json)

echo -e "${GREEN}✓ Tokens created successfully${NC}"
echo ""

# Step 8: Display export URLs
echo -e "${YELLOW}Step 8: Export URLs created:${NC}"
echo ""
echo "USER (owned sites only):"
echo "  http://localhost:8000/export/user_owned/${USER_TOKEN}/${USER_EMAIL}.csv"
echo ""
echo "USER (all sites):"
echo "  http://localhost:8000/export/user_all/${USER_TOKEN}/${USER_EMAIL}.csv"
echo ""
echo "PROJECT:"
echo "  http://localhost:8000/export/project/${PROJECT_TOKEN}/${PROJECT_SLUG}.csv"
echo ""
echo "SITE:"
echo "  http://localhost:8000/export/site/${SITE_TOKEN}/${SITE_NAME}.csv"
echo ""

# Step 9: Test each export endpoint
echo -e "${YELLOW}Step 9: Testing export endpoints...${NC}"
echo ""

# Function to test an endpoint
test_endpoint() {
    local name=$1
    local url=$2

    echo -n "Testing ${name}... "

    # Make request and check response
    response=$(curl -s -o /dev/null -w "%{http_code}" "$url")

    if [ "$response" = "200" ]; then
        # Get actual data to verify it's CSV
        data=$(curl -s "$url" | head -1)
        if [[ $data == *","* ]]; then
            echo -e "${GREEN}✓ OK${NC} (HTTP $response, valid CSV)"
        else
            echo -e "${YELLOW}⚠ WARNING${NC} (HTTP $response, but response doesn't look like CSV)"
            echo "  First line: $data"
        fi
    else
        echo -e "${RED}✗ FAILED${NC} (HTTP $response)"
        # Show error details
        error=$(curl -s "$url" | head -5)
        echo "  Error: $error"
    fi
}

# Test all endpoints
test_endpoint "USER owned sites" "http://localhost:8000/export/user_owned/${USER_TOKEN}/${USER_EMAIL}.csv"
test_endpoint "USER all sites" "http://localhost:8000/export/user_all/${USER_TOKEN}/${USER_EMAIL}.csv"
if [ "$PROJECT_TOKEN" != "NONE" ]; then
    test_endpoint "PROJECT sites" "http://localhost:8000/export/project/${PROJECT_TOKEN}/${PROJECT_SLUG}.csv"
else
    echo "Skipping PROJECT test (no projects in database)"
fi
if [ "$SITE_TOKEN" != "NONE" ]; then
    test_endpoint "SITE" "http://localhost:8000/export/site/${SITE_TOKEN}/${SITE_NAME}.csv"
else
    echo "Skipping SITE test (no sites in database)"
fi

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Export System Migration Test Complete!${NC}"
echo -e "${GREEN}=========================================${NC}"
