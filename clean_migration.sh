#!/bin/bash

# Script to regenerate clean migration 0052 without drift

set -e

echo "========================================="
echo "Clean Migration Regeneration"
echo "========================================="
echo ""

# Step 1: Stash current migration files
echo "Step 1: Backing up current migration files..."
cp terraso_backend/apps/core/migrations/0052_add_export_token_to_user.py /tmp/0052_backup.py
cp terraso_backend/apps/core/migrations/0053_create_system_export_user.py /tmp/0053_backup.py
echo "✓ Backed up to /tmp/"

# Step 2: Delete the export migrations
echo ""
echo "Step 2: Removing export migrations..."
rm terraso_backend/apps/core/migrations/0052_add_export_token_to_user.py
rm terraso_backend/apps/core/migrations/0053_create_system_export_user.py
echo "✓ Removed"

# Step 3: Reset to clean state (main branch migrations)
echo ""
echo "Step 3: Migrating to main branch state (0051)..."
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py migrate core 0051
echo "✓ Migrated to 0051"

# Step 4: Run makemigrations to catch any drift
echo ""
echo "Step 4: Running makemigrations to catch model drift..."
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py makemigrations core
echo ""
echo "If Django created a migration for drift, review it and commit it separately."
echo "Press Enter to continue with export migration..."
read

# Step 5: Now regenerate the export migration cleanly
echo ""
echo "Step 5: Regenerating export migration (0052)..."
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py makemigrations core --name add_export_token_to_user

# Step 6: Restore the 0053 migration
echo ""
echo "Step 6: Restoring 0053 migration..."
cp /tmp/0053_backup.py terraso_backend/apps/core/migrations/0053_create_system_export_user.py
echo "✓ Restored 0053"

echo ""
echo "========================================="
echo "Done! Review the new migrations:"
echo "  - Check if a drift migration was created"
echo "  - Check the new 0052 migration"
echo "  - Test with: ./test_1_setup_db.sh"
echo "========================================="
