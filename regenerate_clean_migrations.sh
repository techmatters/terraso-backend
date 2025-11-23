#!/bin/bash

# Script to regenerate clean export migrations without drift

set -e

echo "========================================="
echo "Clean Migration Regeneration"
echo "========================================="
echo ""

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Step 1: Backup current migrations
echo -e "${YELLOW}Step 1: Backing up current migration files...${NC}"
cp terraso_backend/apps/core/migrations/0052_add_export_token_to_user.py /tmp/0052_backup.py
cp terraso_backend/apps/core/migrations/0053_create_system_export_user.py /tmp/0053_backup.py
cp terraso_backend/apps/project_management/migrations/0029_add_export_token_to_project_and_site.py /tmp/0029_backup.py
echo -e "${GREEN}✓ Backed up to /tmp/${NC}"
echo ""

# Step 2: Delete ALL export migrations
echo -e "${YELLOW}Step 2: Removing export migrations...${NC}"
rm terraso_backend/apps/core/migrations/0052_add_export_token_to_user.py
rm terraso_backend/apps/core/migrations/0053_create_system_export_user.py
rm terraso_backend/apps/project_management/migrations/0029_add_export_token_to_project_and_site.py
echo -e "${GREEN}✓ Removed${NC}"
echo ""

# Step 3: Reset database to clean state
echo -e "${YELLOW}Step 3: Resetting database to clean state...${NC}"
./test_1_setup_db.sh
echo ""

# Step 4: Check for drift (should be none)
echo -e "${YELLOW}Step 4: Checking for model drift...${NC}"
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py makemigrations --dry-run
echo ""
echo "If Django says 'No changes detected', proceed. Otherwise review the drift."
echo "Press Enter to continue..."
read
echo ""

# Step 5: Generate clean migrations
echo -e "${YELLOW}Step 5: Generating clean export migrations...${NC}"
echo "Generating core migration (User.export_token)..."
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py makemigrations core --name add_export_token_to_user
echo ""
echo "Generating project_management migration (Project/Site.export_token)..."
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py makemigrations project_management --name add_export_token_to_project_and_site
echo -e "${GREEN}✓ Generated${NC}"
echo ""

# Step 6: Restore system user migration
echo -e "${YELLOW}Step 6: Restoring system user migration (0053)...${NC}"
cp /tmp/0053_backup.py terraso_backend/apps/core/migrations/0053_create_system_export_user.py
echo -e "${GREEN}✓ Restored 0053${NC}"
echo ""

# Step 7: Test the new migrations
echo -e "${YELLOW}Step 7: Testing new migrations...${NC}"
echo "Running test_2_test_exports.sh to apply and test migrations..."
./test_2_test_exports.sh

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Done! Check the new migrations:${NC}"
echo "  - terraso_backend/apps/core/migrations/0052_add_export_token_to_user.py"
echo "  - terraso_backend/apps/project_management/migrations/0029_add_export_token_to_project_and_site.py"
echo "  - (0053 was restored unchanged)"
echo -e "${GREEN}=========================================${NC}"
