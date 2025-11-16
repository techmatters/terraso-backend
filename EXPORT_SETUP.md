# Export System Setup Instructions

## Overview

The export functionality uses:
1. **Export Tokens** - UUID-based tokens that map to specific resources (User, Project, or Site)
2. **System User** (`system-export@terraso.org`) - Bypasses user-based security checks

## Export Tokens

Export tokens provide secure, shareable access to export endpoints. Each token is a UUID that maps to a specific resource.

### Permission Model

**Who can create/delete/view export tokens?**

- **USER tokens**: Only the user themselves
- **PROJECT tokens**: Only project managers and owners
- **SITE tokens**:
  - For unaffiliated sites: Only the site owner
  - For project sites: Only project managers and owners

**Who can use export tokens to download data?**
- Anyone with a valid token (no authentication required)
- Tokens act as bearer tokens - possession of the token grants access

**What happens when resources are deleted?**
- When a user is (soft) deleted, their export tokens are automatically deleted
- When a project is (soft) deleted, its export tokens are automatically deleted
- When a site is (soft) deleted, its export tokens are automatically deleted

### Creating Export Tokens (GraphQL)

Use the mobile client or GraphQL interface to create tokens:

```graphql
mutation {
  createExportToken(resourceType: USER, resourceId: "user-uuid-here") {
    token {
      token
      resourceType
      resourceId
    }
  }
}
```

**Resource Types**: `USER`, `PROJECT`, `SITE`

### Deleting Export Tokens (GraphQL)

```graphql
mutation {
  deleteExportToken(token: "550e8400-e29b-41d4-a716-446655440000") {
    success
  }
}
```

### Querying Export Tokens (GraphQL)

```graphql
query {
  exportToken(resourceType: USER, resourceId: "user-uuid-here") {
    token
    resourceType
    resourceId
  }
}
```

## Available Export Endpoints

All endpoints now use **export tokens** instead of raw IDs for security:

1. **Project Export**: `/export/project/{project_token}/{project_name}.{format}`
   - Exports all sites within a specific project

2. **Site Export**: `/export/site/{site_token}/{site_name}.{format}`
   - Exports a single site with all its data

3. **User Owned Sites Export**: `/export/user_owned/{user_token}/{user_name}.{format}`
   - Exports all sites owned by a user (not part of any project)

4. **User All Sites Export**: `/export/user_all/{user_token}/{user_name}.{format}`
   - Exports all sites owned by user PLUS all sites in projects where user is a member

**Supported formats**: `csv`, `json`

**Note on Unaffiliated Sites**: Sites not associated with any project will have `projectName: null` in exports. This is handled correctly by the export system.

**Example URLs** (with tokens):
- `http://localhost:8000/export/project/550e8400-e29b-41d4-a716-446655440000/my-project.csv`
- `http://localhost:8000/export/site/a1b2c3d4-e5f6-7890-abcd-ef1234567890/my-site.json`
- `http://localhost:8000/export/user_owned/f47ac10b-58cc-4372-a567-0e02b2c3d479/john-doe.csv`
- `http://localhost:8000/export/user_all/f47ac10b-58cc-4372-a567-0e02b2c3d479/john-doe.json`

## Creating the System Export User

The system export user (`system-export@terraso.org`) is **automatically created** by migration `0054_create_system_export_user`.

When you run migrations (`python manage.py migrate`), this user will be created if it doesn't already exist.

### Manual Creation (Only if Needed)

If for some reason you need to create this user manually:

#### For Local Development

```bash
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py shell -c "from apps.core.models import User; user, created = User.objects.get_or_create(email='system-export@terraso.org', defaults={'first_name': 'System', 'last_name': 'Export'}); print(f'User {user.email} {\"created\" if created else \"already exists\"}')"
```

#### Via Django Admin

1. Log into Django admin: `/admin/`
2. Navigate to Users → Add user
3. Create user with:
   - **Email**: `system-export@terraso.org`
   - **First name**: `System`
   - **Last name**: `Export`
4. Save

## Verification

To verify the user exists in a specific database:

```bash
# Local
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py shell -c "from apps.core.models import User; print(User.objects.filter(email='system-export@terraso.org').exists())"

# With specific DATABASE_URL
DATABASE_URL="<your-database-url>" \
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py shell -c "from apps.core.models import User; print(User.objects.filter(email='system-export@terraso.org').exists())"
```

Expected output: `True` (if user exists) or `False` (if user doesn't exist)

## Technical Details

### Why is this user needed?

The export system needs to:
1. Bypass user-based security filtering (membership checks)
2. Access all projects/sites regardless of ownership
3. Have a traceable identity in logs and audit trails

### How it works

- Export views (`project_export`, `site_export`) set `request.user` to this system user
- They also set `request.is_system_export = True` flag
- GraphQL `get_queryset()` methods check for this flag and bypass filtering
- This allows exports to access all data without being limited to a specific user's permissions

### Security Considerations

**Token Security:**
- UUID4 tokens have 122 bits of randomness (~5.3 × 10^36 possible values)
- Brute force attacks are computationally infeasible
- Tokens themselves are cryptographically unguessable

**Permission-Based Protection:**
- GraphQL mutations/queries require authentication and proper permissions
- Users can only create/view/delete tokens for resources they manage
- Prevents enumeration attacks via GraphQL

**Bearer Token Model:**
- Export URLs use `@auth_optional` - no authentication required beyond the token
- Anyone with a token can download the data
- Share tokens carefully (via secure channels)

**Token Management:**
- Each resource (User/Project/Site) stores one export_token field referencing their current token
- Multiple ExportToken records can exist per resource, but only one is "active" (stored in the resource's export_token field)
- Tokens are stored in the `export_token` table with mappings to resources
- Tokens are automatically deleted when their resource is soft-deleted (User, Project, or Site)
- Creating a new token replaces the old token reference on the resource

**Current Limitations:**
- Tokens do not expire (consider adding expiration)
- No rate limiting on export endpoints (consider adding)
- No audit logging of token usage (consider adding)

