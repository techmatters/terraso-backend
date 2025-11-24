#!/bin/bash
set -e

# Default to local database if no argument provided
DEFAULT_DB_URL="postgresql://postgres:postgres@localhost:5432/terraso_backend"

# Use command-line argument if provided, otherwise use default
if [ -n "$1" ]; then
    DB_URL="$1"
else
    DB_URL="$DEFAULT_DB_URL"
fi

echo "=========================================="
echo "Export Token Table Dump"
echo "=========================================="
echo ""
echo "Database: $DB_URL" | sed 's/:.*@/:***@/'  # Hide password in output
echo ""

# Dump the export_token table with nice formatting
echo "Querying export_token table..."
echo ""

# Run the main queries (stderr will be handled separately for the last section)
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
    user_id,
    CASE
        WHEN LENGTH(token) > 0 THEN 'Valid'
        ELSE 'Invalid'
    END as status
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
echo "=== TOKENS BY USER (READABLE) ==="
echo ""

# Run the readable tokens query separately and clean up the output
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
        -- Get user email or show ID if not found
        IF user_rec.email IS NOT NULL THEN
            user_email := user_rec.email || ' (' || user_rec.user_id || ')';
        ELSE
            user_email := 'Unknown User (' || user_rec.user_id || ')';
        END IF;

        RAISE NOTICE '%', user_email;

        -- Show all tokens for this user
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
            -- Build resource description with ID
            IF token_rec.resource_type = 'USER' THEN
                IF token_rec.resource_user_email != '' THEN
                    resource_name := 'USER ' || token_rec.resource_user_email || ' (' || token_rec.resource_id || ')';
                ELSE
                    resource_name := 'USER (unknown) (' || token_rec.resource_id || ')';
                END IF;
            ELSIF token_rec.resource_type = 'PROJECT' THEN
                IF token_rec.project_name != '' THEN
                    resource_name := 'PROJECT "' || token_rec.project_name || '" (' || token_rec.resource_id || ')';
                ELSE
                    resource_name := 'PROJECT (unknown) (' || token_rec.resource_id || ')';
                END IF;
            ELSIF token_rec.resource_type = 'SITE' THEN
                IF token_rec.site_name != '' THEN
                    resource_name := 'SITE "' || token_rec.site_name || '" (' || token_rec.resource_id || ')';
                ELSE
                    resource_name := 'SITE (unknown) (' || token_rec.resource_id || ')';
                END IF;
            ELSE
                resource_name := token_rec.resource_type || ' (' || token_rec.resource_id || ')';
            END IF;

            RAISE NOTICE '    % -> %', token_rec.token, resource_name;
        END LOOP;

        RAISE NOTICE '';
    END LOOP;
END $$;
SQL

echo ""
echo "=========================================="
echo "Dump complete!"
echo "=========================================="
