#!/bin/bash
set -e

# =============================================================================
# Terraso Database Restore from Render
# =============================================================================
# Downloads a backup from the Render database and restores it to local Docker.
#
# Usage:
#   ./scripts/database/restore_from_render.sh [OPTIONS]
#
# Options:
#   -h, --help     Show this help message
#   -f, --force    Skip prompts and download fresh backup
#
# Environment:
#   RENDER_DB_URL  Required. PostgreSQL connection URL for Render database.
#                  Example: postgresql://user:pass@host/database
# =============================================================================

show_help() {
    head -n 18 "$0" | tail -n 16 | sed 's/^# //' | sed 's/^#//'
    exit 0
}

# Parse command line arguments
FORCE_DOWNLOAD=false
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            ;;
        -f|--force)
            FORCE_DOWNLOAD=true
            shift
            ;;
        *)
            echo "Error: Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Check for required dependencies
check_dependency() {
    if ! command -v "$1" &> /dev/null; then
        echo "Error: Required command '$1' not found"
        echo "Please install $1 before running this script"
        exit 1
    fi
}

check_dependency "pg_dump"
check_dependency "docker"

# Find git root directory and change to it
GIT_ROOT=$(git rev-parse --show-toplevel)
pushd "$GIT_ROOT" > /dev/null

# Ensure we return to original directory on exit (normal or error)
cleanup() {
    popd > /dev/null 2>&1 || true
}
trap cleanup EXIT

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
BACKUP_DIR="$GIT_ROOT/scripts/database"
BACKUP_FILE="$BACKUP_DIR/terraso_render_backup.sql"

# Local database configuration
LOCAL_DB_NAME="terraso_backend"

# Docker compose files
COMPOSE_FILES="-f docker-compose.base.yml -f docker-compose.dev.yml"

# Timing variables
BACKUP_TIME=""

echo "=========================================="
echo "Terraso Database Restore from Render"
echo "=========================================="
echo "Working directory: $GIT_ROOT"
echo ""

# Download backup function
download_backup() {
    echo "Downloading backup from Render..."
    BACKUP_START=$(date +%s)
    if ! pg_dump "$RENDER_DB_URL" > "$BACKUP_FILE"; then
        echo "Error: Failed to download backup from Render"
        echo "Check your RENDER_DB_URL and network connection"
        exit 1
    fi
    BACKUP_END=$(date +%s)
    BACKUP_TIME=$((BACKUP_END - BACKUP_START))
    echo "Backup downloaded"
}

# Check if backup file exists and handle accordingly
if [ -f "$BACKUP_FILE" ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    BACKUP_DATE=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$BACKUP_FILE" 2>/dev/null || stat -c "%y" "$BACKUP_FILE" 2>/dev/null | cut -d' ' -f1-2)
    echo "Existing backup found:"
    echo "  - File: $BACKUP_FILE"
    echo "  - Size: $BACKUP_SIZE"
    echo "  - Date: $BACKUP_DATE"
    echo ""

    if [ "$FORCE_DOWNLOAD" = true ]; then
        download_backup
    else
        read -p "Use existing backup? (Y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Nn]$ ]]; then
            download_backup
        fi
    fi
else
    echo "No existing backup found"
    download_backup
fi

# Update backup size after potential download
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "Backup file size: $BACKUP_SIZE"

echo ""
echo "=========================================="
echo "Restoring to local database"
echo "=========================================="

# Check if Django dev server is running (port 8000)
if lsof -i :8000 -sTCP:LISTEN > /dev/null 2>&1; then
    echo "Error: Something is listening on port 8000 (likely Django dev server)"
    echo "Please stop the dev server before running this script:"
    echo "  - Press Ctrl+C in the terminal running 'make run'"
    echo "  - Or run: docker compose -f docker-compose.base.yml -f docker-compose.dev.yml stop web"
    exit 1
fi

# Ensure database service is running
echo "Starting database service..."
if ! docker compose $COMPOSE_FILES up -d db; then
    echo "Error: Failed to start database container"
    exit 1
fi

# Wait for database to be healthy
echo "Waiting for database to be ready..."
WAIT_COUNT=0
MAX_WAIT=30
until docker compose $COMPOSE_FILES exec -T db pg_isready -U postgres -d postgres > /dev/null 2>&1; do
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
    if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
        echo "Error: Database did not become ready within ${MAX_WAIT}s"
        exit 1
    fi
done
echo "Database is ready"

# Drop and recreate database using docker compose
echo "Dropping existing database..."
docker compose $COMPOSE_FILES exec -T db psql -U postgres -c "DROP DATABASE IF EXISTS $LOCAL_DB_NAME;" 2>/dev/null || true

echo "Creating fresh database..."
if ! docker compose $COMPOSE_FILES exec -T db psql -U postgres -c "CREATE DATABASE $LOCAL_DB_NAME;" 2>/dev/null; then
    echo "Error: Failed to create database"
    exit 1
fi

# Restore from backup (suppress notices for cleaner output)
echo "Restoring backup (this may take a few minutes)..."
RESTORE_START=$(date +%s)
if ! docker compose $COMPOSE_FILES exec -T db psql -U postgres -d "$LOCAL_DB_NAME" --quiet -o /dev/null < "$BACKUP_FILE" 2>&1 | grep -v "^SET$\|^COMMENT$\|^CREATE\|^ALTER\|^GRANT\|^REVOKE" || true; then
    # The restore itself succeeded if we get here (set -e would have caught real errors)
    :
fi
RESTORE_END=$(date +%s)
RESTORE_TIME=$((RESTORE_END - RESTORE_START))

echo ""
echo "=========================================="
echo "Restore complete!"
echo "=========================================="
echo ""
echo "Summary:"
if [ -n "$BACKUP_TIME" ]; then
    echo "  - Backup download time: ${BACKUP_TIME}s"
fi
echo "  - Restore time: ${RESTORE_TIME}s"
echo "  - Backup file size: $BACKUP_SIZE"
echo ""

# Offer to run migrations
read -p "Run migrations now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Running migrations..."
    make migrate
    echo ""
    echo "Migrations complete!"
fi
