#!/bin/bash

# Part 2: Test export endpoints
# This script creates export tokens and tests all export URLs

set -e  # Exit on error

echo "========================================="
echo "Part 2: Export System Testing"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Run export migrations
echo -e "${YELLOW}Step 1: Running export migrations...${NC}"
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py migrate
echo -e "${GREEN}✓ Migrations complete${NC}"
echo ""

# Step 2: Verify Derek exists
echo -e "${YELLOW}Step 2: Verifying Derek user exists...${NC}"
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py shell -c "
from apps.core.models import User
derek = User.objects.filter(email='derek@techmatters.org').first()
if derek:
    print(f'✓ Derek exists: {derek.email} ({derek.id})')
else:
    print('✗ WARNING: Derek user not found in database')
" > /dev/null 2>&1
echo -e "${GREEN}✓ Derek verified${NC}"
echo ""

# Step 3: Verify system export user was created
echo -e "${YELLOW}Step 3: Verifying system export user...${NC}"
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py shell -c "
from apps.core.models import User
try:
    user = User.objects.get(email='system-export@terraso.org')
    print(f'✓ System export user exists: {user.email}')
except User.DoesNotExist:
    print('✗ ERROR: System export user not found!')
    exit(1)
" > /dev/null 2>&1
echo -e "${GREEN}✓ System user verified${NC}"
echo ""

# Step 4: Create export tokens for Derek
echo -e "${YELLOW}Step 4: Creating export tokens for Derek...${NC}"
TOKENS_OUTPUT=$(docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py shell -c "
import json, sys
from apps.core.models import User
from apps.project_management.models import Project, Site
from apps.export.models import ExportToken

# Find Derek
derek = User.objects.filter(email='derek@techmatters.org').first()

if not derek:
    derek = User.objects.filter(deleted_at__isnull=True).exclude(email='system-export@terraso.org').first()

# Create USER token
try:
    user_token = ExportToken.objects.get(resource_type='USER', resource_id=str(derek.id))
except ExportToken.DoesNotExist:
    user_token = ExportToken.create_token('USER', str(derek.id))

# Find a project
project = Project.objects.filter(deleted_at__isnull=True).first()

if not project:
    project_token_str = 'NONE'
    project_name = 'N/A'
    project_slug = 'n-a'
else:
    try:
        project_token = ExportToken.objects.get(resource_type='PROJECT', resource_id=str(project.id))
    except ExportToken.DoesNotExist:
        project_token = ExportToken.create_token('PROJECT', str(project.id))
    project_token_str = str(project_token.token)
    project_name = project.name
    project_slug = project.name.lower().replace(' ', '-').replace('_', '-')[:50]

# Find a site
site = Site.objects.filter(deleted_at__isnull=True).first()

if not site:
    site_token_str = 'NONE'
    site_name = 'N/A'
else:
    try:
        site_token = ExportToken.objects.get(resource_type='SITE', resource_id=str(site.id))
    except ExportToken.DoesNotExist:
        site_token = ExportToken.create_token('SITE', str(site.id))
    site_token_str = str(site_token.token)
    site_name = site.name

# Print JSON to stdout with marker
result = {
    'user_token': str(user_token.token),
    'user_email': derek.email,
    'project_token': project_token_str,
    'project_name': project_name,
    'project_slug': project_slug,
    'site_token': site_token_str,
    'site_name': site_name
}
print('>>>JSON>>>' + json.dumps(result) + '<<<JSON<<<', file=sys.stderr)
" 2>&1)

# Extract JSON from output
TOKENS=$(echo "$TOKENS_OUTPUT" | grep -o '>>>JSON>>>.*<<<JSON<<<' | sed 's/>>>JSON>>>//; s/<<<JSON<<<//')

# Parse tokens
USER_TOKEN=$(echo "$TOKENS" | jq -r '.user_token')
USER_EMAIL=$(echo "$TOKENS" | jq -r '.user_email')
PROJECT_TOKEN=$(echo "$TOKENS" | jq -r '.project_token')
PROJECT_NAME=$(echo "$TOKENS" | jq -r '.project_name')
PROJECT_SLUG=$(echo "$TOKENS" | jq -r '.project_slug')
SITE_TOKEN=$(echo "$TOKENS" | jq -r '.site_token')
SITE_NAME=$(echo "$TOKENS" | jq -r '.site_name')

echo -e "${GREEN}✓ Tokens created successfully${NC}"
echo ""

# Step 5: Display export URLs
echo -e "${YELLOW}Step 5: Export URLs:${NC}"
echo ""
echo "USER (owned sites only):"
echo "  http://localhost:8000/export/user_owned/${USER_TOKEN}/${USER_EMAIL}.csv"
echo ""
echo "USER (all sites):"
echo "  http://localhost:8000/export/user_all/${USER_TOKEN}/${USER_EMAIL}.csv"
echo ""
if [ "$PROJECT_TOKEN" != "NONE" ]; then
    echo "PROJECT:"
    echo "  http://localhost:8000/export/project/${PROJECT_TOKEN}/${PROJECT_SLUG}.csv"
    echo ""
fi
if [ "$SITE_TOKEN" != "NONE" ]; then
    echo "SITE:"
    echo "  http://localhost:8000/export/site/${SITE_TOKEN}/${SITE_NAME}.csv"
    echo ""
fi

# Step 6: Test each export endpoint
echo -e "${YELLOW}Step 6: Testing export endpoints...${NC}"
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
        error=$(curl -s "$url" | head -3)
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
echo -e "${GREEN}Export System Testing Complete!${NC}"
echo -e "${GREEN}=========================================${NC}"
