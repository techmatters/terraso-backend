# Export System Setup Instructions

## Overview

The export functionality uses a system user (`system-export@terraso.org`) to bypass user-based security checks. This user must be created in each database environment.

## Available Export Endpoints

1. **Project Export**: `/export/project/{project_id}/{project_name}.{format}`
   - Exports all sites within a specific project

2. **Site Export**: `/export/site/{site_id}/{site_name}.{format}`
   - Exports a single site with all its data

3. **User Owned Sites Export**: `/export/user_owned/{user_id}/{user_name}.{format}`
   - Exports all sites owned by a user (not part of any project)

4. **User and Projects Sites Export**: `/export/user_and_projects/{user_id}/{user_name}.{format}`
   - Exports all sites owned by user PLUS all sites in projects where user is a member

**Supported formats**: `csv`, `json`

**Example URLs**:
- `http://localhost:8000/export/project/123/my-project.csv`
- `http://localhost:8000/export/site/456/my-site.json`
- `http://localhost:8000/export/user_owned/789/john-doe.csv`
- `http://localhost:8000/export/user_and_projects/789/john-doe.json`

## Creating the System Export User

### For Local Development

```bash
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py shell -c "from apps.core.models import User; user, created = User.objects.get_or_create(email='system-export@terraso.org', defaults={'first_name': 'System', 'last_name': 'Export'}); print(f'User {user.email} {\"created\" if created else \"already exists\"}')"
```

### For Staging Database

```bash
# Option 1: Using Django shell with DATABASE_URL environment variable
DATABASE_URL="postgresql://terraso_pg:0RId44hSOgYXhytjyKvj8Go45ujrCrqW@dpg-cclqslarrk007qgqrjfg-a.oregon-postgres.render.com/terraso_backend_fonz" \
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py shell -c "from apps.core.models import User; user, created = User.objects.get_or_create(email='system-export@terraso.org', defaults={'first_name': 'System', 'last_name': 'Export'}); print(f'User {user.email} {\"created\" if created else \"already exists\"}')"

# Option 2: If deployed on server, SSH into the server and run:
python manage.py shell -c "from apps.core.models import User; user, created = User.objects.get_or_create(email='system-export@terraso.org', defaults={'first_name': 'System', 'last_name': 'Export'}); print(f'User {user.email} {\"created\" if created else \"already exists\"}')"
```

### For Production Database

```bash
# Option 1: Using Django shell with DATABASE_URL environment variable
DATABASE_URL="postgresql://terraso_pg:g5Sl9MzD1BXuo9LOPOxyfPR9dziuNQ0t@dpg-cd6rroirrk04votkd5qg-a.oregon-postgres.render.com/terraso_backend_g8od" \
docker compose -f docker-compose.dev.yml run --rm web python terraso_backend/manage.py shell -c "from apps.core.models import User; user, created = User.objects.get_or_create(email='system-export@terraso.org', defaults={'first_name': 'System', 'last_name': 'Export'}); print(f'User {user.email} {\"created\" if created else \"already exists\"}')"

# Option 2: If deployed on server, SSH into the server and run:
python manage.py shell -c "from apps.core.models import User; user, created = User.objects.get_or_create(email='system-export@terraso.org', defaults={'first_name': 'System', 'last_name': 'Export'}); print(f'User {user.email} {\"created\" if created else \"already exists\"}')"
```

### Alternative: Create via Django Admin

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

- The export URLs use `@auth_optional` decorator - they don't require authentication
- **TODO**: Add export-specific security/authorization
- Consider adding:
  - API key authentication for export endpoints
  - Rate limiting
  - Audit logging of export requests
  - IP allowlisting if exports should only come from specific sources

## Migration Alternative (Optional)

If you want to ensure this user is created automatically during deployment, you can create a Django data migration:

```bash
python manage.py makemigrations --empty core --name create_system_export_user
```

Then edit the migration file:

```python
from django.db import migrations

def create_system_export_user(apps, schema_editor):
    User = apps.get_model('core', 'User')
    User.objects.get_or_create(
        email='system-export@terraso.org',
        defaults={
            'first_name': 'System',
            'last_name': 'Export'
        }
    )

class Migration(migrations.Migration):
    dependencies = [
        ('core', 'XXXX_previous_migration'),
    ]

    operations = [
        migrations.RunPython(create_system_export_user),
    ]
```

This ensures the user is created automatically when migrations run during deployment.
