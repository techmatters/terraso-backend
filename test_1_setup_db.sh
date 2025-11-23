#!/bin/bash

# Part 1: Setup database with migrations
# This script restores the production dump and runs migrations

set -e  # Exit on error

echo "========================================="
echo "Part 1: Database Setup and Migrations"
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
echo "This may take 3-5 minutes..."
cat /tmp/g8od_dump.sql | docker exec -i terraso-backend-db-1 psql -U postgres terraso_backend 2>&1 | tail -5
echo -e "${GREEN}Database restored${NC}"

# Step 3: Check migration state
echo ""
echo -e "${YELLOW}Step 3: Checking migration state...${NC}"
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py showmigrations | grep -E "(core|soil_id|project_management|export)" | tail -20

# Step 4: Run migrations to main branch state only (0051 core, 0028 project_management)
echo ""
echo -e "${YELLOW}Step 4: Running migrations to main branch state...${NC}"
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py migrate core 0051
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py migrate project_management 0028

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Database setup complete!${NC}"
echo -e "${GREEN}Run test_2_test_exports.sh to test exports${NC}"
echo -e "${GREEN}=========================================${NC}"
