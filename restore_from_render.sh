#!/bin/bash
set -e

# Find git root directory and change to it
GIT_ROOT=$(git rev-parse --show-toplevel)
pushd "$GIT_ROOT" > /dev/null

# Check for required environment variable
if [ -z "$RENDER_DB_URL" ]; then
    echo "Error: RENDER_DB_URL environment variable is not set"
    echo ""
    echo "Please set RENDER_DB_URL before running this script:"
    echo "  export RENDER_DB_URL='postgresql://user:pass@host/database'"
    echo ""
    exit 1
fi

# Configuration
BACKUP_DIR="$GIT_ROOT"
BACKUP_FILE="$BACKUP_DIR/terraso_render_backup.sql"

# Local database configuration
LOCAL_DB_HOST="localhost"
LOCAL_DB_PORT="5432"
LOCAL_DB_USER="postgres"
LOCAL_DB_PASSWORD="postgres"
LOCAL_DB_NAME="terraso_backend"

# Timing variables
BACKUP_TIME=""
RESTORE_START=""

echo "=========================================="
echo "Terraso Database Restore from Render"
echo "=========================================="
echo "Working directory: $GIT_ROOT"
echo ""

# Check if backup file exists
if [ -f "$BACKUP_FILE" ]; then
    echo "✓ Backup file found at: $BACKUP_FILE"
    read -p "Do you want to use the existing backup? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Downloading fresh backup from Render..."
        BACKUP_START=$(date +%s)
        pg_dump "$RENDER_DB_URL" > "$BACKUP_FILE"
        BACKUP_END=$(date +%s)
        BACKUP_TIME=$((BACKUP_END - BACKUP_START))
        echo "✓ Fresh backup downloaded"
    fi
else
    echo "Backup file not found. Downloading from Render..."
    BACKUP_START=$(date +%s)
    pg_dump "$RENDER_DB_URL" > "$BACKUP_FILE"
    BACKUP_END=$(date +%s)
    BACKUP_TIME=$((BACKUP_END - BACKUP_START))
    echo "✓ Backup downloaded to: $BACKUP_FILE"
fi

# Check backup file size
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "Backup file size: $BACKUP_SIZE"

echo ""
echo "=========================================="
echo "Restoring to local database"
echo "=========================================="

# Stop any running Django servers to avoid connection issues
echo "Note: Make sure Django dev server is stopped"

# Ensure database service is running
echo "Starting database service if needed..."
docker compose -f docker-compose.base.yml -f docker-compose.dev.yml up -d db

# Wait for database to be healthy
echo "Waiting for database to be ready..."
until docker compose -f docker-compose.base.yml -f docker-compose.dev.yml exec -T db pg_isready -U postgres -d terraso_backend > /dev/null 2>&1; do
    sleep 1
done
echo "✓ Database is ready"

# Drop and recreate database using docker compose
echo "Dropping existing database..."
docker compose -f docker-compose.base.yml -f docker-compose.dev.yml exec -T db psql -U postgres -c "DROP DATABASE IF EXISTS $LOCAL_DB_NAME;" || true

echo "Creating fresh database..."
docker compose -f docker-compose.base.yml -f docker-compose.dev.yml exec -T db psql -U postgres -c "CREATE DATABASE $LOCAL_DB_NAME;"

# Restore from backup
echo "Restoring backup (this may take a minute)..."
RESTORE_START=$(date +%s)
docker compose -f docker-compose.base.yml -f docker-compose.dev.yml exec -T db psql -U postgres -d "$LOCAL_DB_NAME" < "$BACKUP_FILE"
RESTORE_END=$(date +%s)
RESTORE_TIME=$((RESTORE_END - RESTORE_START))

echo ""
echo "=========================================="
echo "✓ Restore complete!"
echo "=========================================="
echo "Database restored from: $BACKUP_FILE"
echo ""
echo "Summary:"
if [ -n "$BACKUP_TIME" ]; then
    echo "  - Backup download time: ${BACKUP_TIME}s"
fi
echo "  - Restore time: ${RESTORE_TIME}s"
echo "  - Backup file size: $BACKUP_SIZE"
echo ""
echo "You can now run migrations if needed."

# Return to original directory
popd > /dev/null
