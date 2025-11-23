#!/bin/bash

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "========================================="
echo "Proper Migration Regeneration"
echo "Phase 1: Generate drift migrations"
echo "Phase 2: Generate export migrations"
echo "========================================="
echo ""

# Phase 1: Generate DRIFT migrations (without export_token)
echo -e "${YELLOW}Phase 1: Generating drift migrations...${NC}"
echo ""

# Step 1: Temporarily remove export_token from models
echo "Step 1: Temporarily removing export_token fields from models..."
grep -n "export_token" terraso_backend/apps/core/models/users.py
grep -n "export_token" terraso_backend/apps/project_management/models/projects.py
grep -n "export_token" terraso_backend/apps/project_management/models/sites.py

echo ""
echo "Found export_token fields. Commenting them out..."
sed -i.bak 's/^    export_token =/    # export_token =/' terraso_backend/apps/core/models/users.py
sed -i.bak 's/^    export_token =/    # export_token =/' terraso_backend/apps/project_management/models/projects.py  
sed -i.bak 's/^    export_token =/    # export_token =/' terraso_backend/apps/project_management/models/sites.py
echo -e "${GREEN}✓ Commented out export_token fields${NC}"
echo ""

# Step 2: Generate drift migrations
echo "Step 2: Generating drift migrations..."
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py makemigrations
echo ""

# Step 3: Restore export_token fields
echo "Step 3: Restoring export_token fields..."
mv terraso_backend/apps/core/models/users.py.bak terraso_backend/apps/core/models/users.py
mv terraso_backend/apps/project_management/models/projects.py.bak terraso_backend/apps/project_management/models/projects.py
mv terraso_backend/apps/project_management/models/sites.py.bak terraso_backend/apps/project_management/models/sites.py
echo -e "${GREEN}✓ Restored export_token fields${NC}"
echo ""

echo -e "${YELLOW}Phase 2: Generating export migrations...${NC}"
echo ""

# Step 4: Generate export_token migrations  
echo "Step 4: Generating clean export migrations..."
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py makemigrations core --name add_export_token_to_user
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py makemigrations project_management --name add_export_token_to_project_and_site
echo -e "${GREEN}✓ Generated export migrations${NC}"
echo ""

# Step 5: Restore system user migration
echo "Step 5: Restoring system user migration..."
cp /tmp/0053_backup.py terraso_backend/apps/core/migrations/
# Find the new number
NEW_NUM=$(ls terraso_backend/apps/core/migrations/ | grep -E "^[0-9]+" | tail -1 | grep -oE "^[0-9]+")
NEW_NUM=$((NEW_NUM + 1))
NEW_NUM=$(printf "%04d" $NEW_NUM)
cp /tmp/0053_backup.py terraso_backend/apps/core/migrations/${NEW_NUM}_create_system_export_user.py
echo -e "${GREEN}✓ Restored as ${NEW_NUM}_create_system_export_user.py${NC}"
echo ""

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Done! Review the new migrations${NC}"
echo -e "${GREEN}=========================================${NC}"
ls -la terraso_backend/apps/core/migrations/ | tail -10
ls -la terraso_backend/apps/project_management/migrations/ | tail -5
ls -la terraso_backend/apps/shared_data/migrations/ | tail -3
ls -la terraso_backend/apps/story_map/migrations/ | tail -3
