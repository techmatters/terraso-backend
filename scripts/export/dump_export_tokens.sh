#!/bin/bash
set -e

# =============================================================================
# Export Token Dump
# =============================================================================
# Shows export tokens and their download URLs, grouped by user.
#
# Usage:
#   ./scripts/export/dump_export_tokens.sh [OPTIONS] [DATABASE_URL]
#
# Options:
#   -h, --help     Show this help message
#   -v, --verbose  Show detailed token data and statistics
#
# Arguments:
#   DATABASE_URL   PostgreSQL connection URL (optional)
#                  Default: postgresql://postgres:postgres@localhost:5432/terraso_backend
#
# Examples:
#   ./scripts/export/dump_export_tokens.sh
#   ./scripts/export/dump_export_tokens.sh -v
#   ./scripts/export/dump_export_tokens.sh "$RENDER_DB_URL"
# =============================================================================

show_help() {
    head -n 22 "$0" | tail -n 20 | sed 's/^# //' | sed 's/^#//'
    exit 0
}

# Parse command line arguments
VERBOSE=false
DB_URL=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        *)
            # Assume it's the database URL
            DB_URL="$1"
            shift
            ;;
    esac
done

# Default database URL if not provided
if [ -z "$DB_URL" ]; then
    DB_URL="postgresql://postgres:postgres@localhost:5432/terraso_backend"
fi

# Check for psql
if ! command -v psql &> /dev/null; then
    echo "Error: psql command not found"
    echo "Please install PostgreSQL client tools"
    exit 1
fi

# Determine base URL from database URL
DB_NAME=$(echo "$DB_URL" | awk -F'/' '{print $NF}')
if [[ "$DB_URL" == *"@localhost"* ]]; then
    BASE_URL="http://localhost:8000"
elif [[ "$DB_NAME" == "terraso_backend_g8od" ]]; then
    BASE_URL="https://api.terraso.org"
elif [[ "$DB_NAME" == "terraso_backend_fonz" ]]; then
    BASE_URL="https://api.staging.terraso.net"
else
    # Extract host:port from DB URL and use https
    DB_HOST=$(echo "$DB_URL" | sed -E 's|.*@([^/]+)/.*|\1|')
    BASE_URL="https://${DB_HOST}"
fi

echo "=========================================="
echo "Export Token Dump"
echo "=========================================="
echo ""
echo "Database: $(echo "$DB_URL" | sed 's/:.*@/:***@/')"
echo "Base URL: $BASE_URL"
echo ""

if [ "$VERBOSE" = true ]; then
    # Full verbose output with all tables
    psql "$DB_URL" <<'SQL'
-- Show table structure
\echo '=== TABLE STRUCTURE ==='
\d export_token

\echo ''
\echo '=== TOKEN DATA ==='

-- Show all tokens with formatted output
SELECT
    token,
    resource_type,
    resource_id,
    user_id
FROM export_token
ORDER BY resource_type, resource_id, user_id;

\echo ''
\echo '=== TOKEN STATISTICS ==='

-- Count tokens by resource type
SELECT
    resource_type,
    COUNT(*) as token_count,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(DISTINCT resource_id) as unique_resources
FROM export_token
GROUP BY resource_type
ORDER BY resource_type;

\echo ''
\echo '=== TOKENS PER USER ==='

-- Show how many tokens each user has
SELECT
    user_id,
    COUNT(*) as total_tokens,
    COUNT(CASE WHEN resource_type = 'USER' THEN 1 END) as user_tokens,
    COUNT(CASE WHEN resource_type = 'PROJECT' THEN 1 END) as project_tokens,
    COUNT(CASE WHEN resource_type = 'SITE' THEN 1 END) as site_tokens
FROM export_token
GROUP BY user_id
ORDER BY total_tokens DESC;

\echo ''
\echo '=== DUPLICATE CHECK ==='

-- Check for any duplicates (should be none with unique constraint)
SELECT
    user_id,
    resource_type,
    resource_id,
    COUNT(*) as duplicate_count
FROM export_token
GROUP BY user_id, resource_type, resource_id
HAVING COUNT(*) > 1;

SQL

    echo ""
    echo "=== TOKENS BY USER (DETAILED) ==="
    echo ""

    # Show tokens with raw token values
    psql "$DB_URL" -t <<'SQL' 2>&1 | grep -v "^DO$" | grep -v "^SET$" | sed 's/^NOTICE:  //'
DO $$
DECLARE
    user_rec RECORD;
    token_rec RECORD;
    user_email TEXT;
    resource_name TEXT;
BEGIN
    FOR user_rec IN
        SELECT DISTINCT et.user_id, u.email
        FROM export_token et
        LEFT JOIN core_user u ON u.id::text = et.user_id
        ORDER BY u.email NULLS LAST, et.user_id
    LOOP
        IF user_rec.email IS NOT NULL THEN
            user_email := user_rec.email;
        ELSE
            user_email := 'Unknown User (' || user_rec.user_id || ')';
        END IF;

        RAISE NOTICE '%', user_email;

        FOR token_rec IN
            SELECT
                et.token,
                et.resource_type,
                et.resource_id,
                COALESCE(u.email, '') as resource_user_email,
                COALESCE(p.name, '') as project_name,
                COALESCE(s.name, '') as site_name
            FROM export_token et
            LEFT JOIN core_user u ON et.resource_type = 'USER' AND u.id::text = et.resource_id
            LEFT JOIN project_management_project p ON et.resource_type = 'PROJECT' AND p.id::text = et.resource_id
            LEFT JOIN project_management_site s ON et.resource_type = 'SITE' AND s.id::text = et.resource_id
            WHERE et.user_id = user_rec.user_id
            ORDER BY et.resource_type, et.resource_id
        LOOP
            IF token_rec.resource_type = 'USER' THEN
                IF token_rec.resource_user_email != '' THEN
                    resource_name := 'USER ' || token_rec.resource_user_email;
                ELSE
                    resource_name := 'USER (unknown)';
                END IF;
            ELSIF token_rec.resource_type = 'PROJECT' THEN
                IF token_rec.project_name != '' THEN
                    resource_name := 'PROJECT "' || token_rec.project_name || '"';
                ELSE
                    resource_name := 'PROJECT (unknown)';
                END IF;
            ELSIF token_rec.resource_type = 'SITE' THEN
                IF token_rec.site_name != '' THEN
                    resource_name := 'SITE "' || token_rec.site_name || '"';
                ELSE
                    resource_name := 'SITE (unknown)';
                END IF;
            ELSE
                resource_name := token_rec.resource_type;
            END IF;

            RAISE NOTICE '    % -> %', token_rec.token, resource_name;
        END LOOP;

        RAISE NOTICE '';
    END LOOP;
END $$;
SQL

else
    # Default: show download URLs grouped by user
    echo "=== EXPORT URLS BY USER ==="
    echo ""

    # Run query and prepend base URL to paths
    psql "$DB_URL" -t <<'SQL' 2>&1 | grep -v "^DO$" | grep -v "^SET$" | sed 's/^NOTICE:  //' | sed "s|/export/|${BASE_URL}/export/|g"
DO $$
DECLARE
    user_rec RECORD;
    token_rec RECORD;
    user_email TEXT;
    url_name TEXT;
    url_path TEXT;
BEGIN
    FOR user_rec IN
        SELECT DISTINCT et.user_id, u.email
        FROM export_token et
        LEFT JOIN core_user u ON u.id::text = et.user_id
        ORDER BY u.email NULLS LAST, et.user_id
    LOOP
        IF user_rec.email IS NOT NULL THEN
            user_email := user_rec.email;
        ELSE
            user_email := 'Unknown (' || LEFT(user_rec.user_id, 8) || '...)';
        END IF;

        RAISE NOTICE '%', user_email;

        FOR token_rec IN
            SELECT
                et.token,
                et.resource_type,
                et.resource_id,
                COALESCE(u.email, '') as resource_user_email,
                COALESCE(p.name, '') as project_name,
                COALESCE(s.name, '') as site_name
            FROM export_token et
            LEFT JOIN core_user u ON et.resource_type = 'USER' AND u.id::text = et.resource_id
            LEFT JOIN project_management_project p ON et.resource_type = 'PROJECT' AND p.id::text = et.resource_id
            LEFT JOIN project_management_site s ON et.resource_type = 'SITE' AND s.id::text = et.resource_id
            WHERE et.user_id = user_rec.user_id
            ORDER BY et.resource_type, et.resource_id
        LOOP
            IF token_rec.resource_type = 'USER' THEN
                -- User tokens have two URLs: owned sites and all sites
                IF token_rec.resource_user_email != '' THEN
                    url_name := REPLACE(SPLIT_PART(token_rec.resource_user_email, '@', 1), '.', '_');
                ELSE
                    url_name := 'user';
                END IF;

                -- My Sites (owned)
                RAISE NOTICE '    My Sites (owned by me)';
                url_path := '/export/token/user_owned/' || token_rec.token || '/' || url_name || '_my_sites.html';
                RAISE NOTICE '        %', url_path;

                -- All Sites (including shared)
                RAISE NOTICE '    All Sites (owned + shared with me)';
                url_path := '/export/token/user_all/' || token_rec.token || '/' || url_name || '_all_sites.html';
                RAISE NOTICE '        %', url_path;

            ELSIF token_rec.resource_type = 'PROJECT' THEN
                IF token_rec.project_name != '' THEN
                    -- Slugify: lowercase, replace non-alphanumeric with underscores
                    url_name := LOWER(REGEXP_REPLACE(token_rec.project_name, '[^a-zA-Z0-9]+', '_', 'g'));
                    url_name := TRIM(BOTH '_' FROM url_name);
                    RAISE NOTICE '    Project "%"', token_rec.project_name;
                ELSE
                    url_name := 'project';
                    RAISE NOTICE '    Project (unknown)';
                END IF;

                url_path := '/export/token/project/' || token_rec.token || '/' || url_name || '.html';
                RAISE NOTICE '        %', url_path;

            ELSIF token_rec.resource_type = 'SITE' THEN
                IF token_rec.site_name != '' THEN
                    url_name := LOWER(REGEXP_REPLACE(token_rec.site_name, '[^a-zA-Z0-9]+', '_', 'g'));
                    url_name := TRIM(BOTH '_' FROM url_name);
                    RAISE NOTICE '    Site "%"', token_rec.site_name;
                ELSE
                    url_name := 'site';
                    RAISE NOTICE '    Site (unknown)';
                END IF;

                url_path := '/export/token/site/' || token_rec.token || '/' || url_name || '.html';
                RAISE NOTICE '        %', url_path;
            END IF;
        END LOOP;

        RAISE NOTICE '';
    END LOOP;
END $$;
SQL

fi

echo ""
echo "=========================================="
echo "Done"
echo "=========================================="
