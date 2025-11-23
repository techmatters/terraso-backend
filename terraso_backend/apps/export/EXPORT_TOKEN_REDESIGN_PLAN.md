# Export Token Redesign Implementation Plan

## ✅ IMPLEMENTATION STATUS: COMPLETED

This redesign has been fully implemented. All changes described in this document have been applied to the codebase.

## Executive Summary

This plan outlined the changes needed to transform the export token system from a resource-centric model (where tokens are stored on User/Project/Site models) to a user-centric model (where tokens are associated with specific users for specific resources).

**Implementation completed on:** 2025-11-23

## Current Architecture

### Database Schema

**ExportToken Model** (`apps/export/models.py:21-53`)
```python
class ExportToken(models.Model):
    token = models.CharField(max_length=36, primary_key=True)  # UUID4
    resource_type = models.CharField(max_length=10, choices=RESOURCE_TYPES)
    resource_id = models.CharField(max_length=255)

    # Index on [resource_type, resource_id]
```

**Resource Models** have `export_token` fields:
- `User.export_token` (`apps/core/models/users.py:86`)
- `Project.export_token` (`apps/project_management/models/projects.py:80`)
- `Site.export_token` (`apps/project_management/models/sites.py:76`)

All three fields are: `CharField(max_length=36, null=True, blank=True, unique=True)`

### Current Data Flow

1. **Token Creation** (`graphql/mutations.py:103-174`):
   - User requests token via GraphQL mutation
   - Permission check via `can_manage_export_token()`
   - Check if `resource.export_token` already exists
   - If not, create `ExportToken` entry and store token on resource model
   - Return token to user

2. **Token Query** (`graphql/queries.py:37-72`):
   - User queries for token by resource_type and resource_id
   - Permission check
   - Lookup in `ExportToken` table
   - Return token object

3. **Token Deletion** (`graphql/mutations.py:184-219`):
   - User deletes token by token string
   - Permission check
   - Clear `export_token` field on resource
   - Delete `ExportToken` entry

4. **Token Usage** (`views.py:28-37`):
   - Public URL contains token (e.g., `/export/token/user_all/{token}/...`)
   - `_resolve_export_token()` looks up token in `ExportToken` table
   - Returns `(resource_type, resource_id)`
   - Request proceeds with system user

### Current Cleanup (Signals)

**Signal Handlers** (`signals.py`):
- `delete_user_export_tokens_on_soft_delete` (line 27-44)
- `delete_project_export_tokens_on_soft_delete` (line 47-64)
- `delete_site_export_tokens_on_soft_delete` (line 67-84)

Each handler:
1. Triggers on `post_save` when `deleted_at` is set
2. Deletes matching `ExportToken` entries
3. Clears `export_token` field on resource

**Missing Cleanup**:
- No handler for user removed from project (should delete user's tokens for that project and its sites)

## Desired Architecture

### New Database Schema

**ExportToken Model** (modified):
```python
class ExportToken(models.Model):
    token = models.CharField(max_length=36, primary_key=True)  # UUID4
    resource_type = models.CharField(max_length=10, choices=RESOURCE_TYPES)
    resource_id = models.CharField(max_length=255)
    user_id = models.CharField(max_length=255)  # NEW FIELD

    class Meta:
        indexes = [
            models.Index(fields=["token"]),  # primary key, automatic
            models.Index(fields=["user_id", "resource_type", "resource_id"]),  # NEW
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "resource_type", "resource_id"],
                name="unique_user_resource_token"
            )
        ]
```

**Resource Models**: Remove `export_token` fields from:
- `User` model
- `Project` model
- `Site` model

### New Data Flow

1. **Token Creation**:
   - User requests token via GraphQL mutation
   - Permission check (unchanged)
   - Lookup: `ExportToken.objects.get(user_id=user.id, resource_type=..., resource_id=...)`
   - If exists, return existing token
   - If not, create new token with `user_id=user.id`
   - No changes to resource models

2. **Token Query**:
   - User queries for token by resource_type and resource_id
   - Permission check (unchanged)
   - Lookup: `ExportToken.objects.get(user_id=user.id, resource_type=..., resource_id=...)`
   - Return token object

3. **Token Deletion**:
   - User deletes token by token string
   - Lookup: `ExportToken.objects.get(token=token)`
   - Permission check (unchanged)
   - Delete `ExportToken` entry
   - No changes to resource models

4. **Token Usage** (unchanged):
   - Lookup by token still works: `ExportToken.objects.get(token=token)`
   - Returns `(resource_type, resource_id, user_id)`
   - Could use `user_id` for future audit logging

### New Cleanup (Signals)

1. **User Deletion** (modified):
   ```python
   @receiver(post_save, sender=User)
   def delete_user_export_tokens_on_soft_delete(sender, instance, **kwargs):
       if instance.deleted_at is not None:
           # Delete ALL tokens created by this user
           ExportToken.objects.filter(user_id=str(instance.id)).delete()
   ```

2. **Project Deletion** (modified):
   ```python
   @receiver(post_save, sender=Project)
   def delete_project_export_tokens_on_soft_delete(sender, instance, **kwargs):
       if instance.deleted_at is not None:
           # Delete all tokens for this project (any user)
           ExportToken.objects.filter(
               resource_type="PROJECT",
               resource_id=str(instance.id)
           ).delete()
   ```

3. **Site Deletion** (modified):
   ```python
   @receiver(post_save, sender=Site)
   def delete_site_export_tokens_on_soft_delete(sender, instance, **kwargs):
       if instance.deleted_at is not None:
           # Delete all tokens for this site (any user)
           ExportToken.objects.filter(
               resource_type="SITE",
               resource_id=str(instance.id)
           ).delete()
   ```

4. **User Removed from Project** (NEW):
   ```python
   @receiver(post_delete, sender=Membership)  # or appropriate signal
   def delete_export_tokens_on_membership_removal(sender, instance, **kwargs):
       if instance.membership_list.project:
           project = instance.membership_list.project
           user_id = str(instance.user.id)

           # Delete user's token for this project
           ExportToken.objects.filter(
               user_id=user_id,
               resource_type="PROJECT",
               resource_id=str(project.id)
           ).delete()

           # Delete user's tokens for all sites in this project
           site_ids = project.sites.values_list('id', flat=True)
           ExportToken.objects.filter(
               user_id=user_id,
               resource_type="SITE",
               resource_id__in=[str(sid) for sid in site_ids]
           ).delete()
   ```

## Implementation Steps

### Phase 1: Database Migration

**File**: `apps/export/migrations/0002_add_user_id_to_export_token.py`

```python
# Migration operations:
# 1. Add user_id field (nullable initially)
# 2. Add composite index on [user_id, resource_type, resource_id]
# 3. Add unique constraint on [user_id, resource_type, resource_id]
# 4. Remove export_token field from User model
# 5. Remove export_token field from Project model
# 6. Remove export_token field from Site model
```

**Note**: Since migrations 0053 (User), 0029 (Project), and 0030 (Site) were never applied to production, we don't need to preserve reverse migrations. We'll simply start from a clean database backup from before those migrations were added.

**Actions**:
1. Restore test database from backup (before export_token fields were added)
2. Run new migration that creates ExportToken with user_id from the start
3. No data migration needed (starting fresh)

### Phase 2: Model Changes

**File**: `apps/export/models.py`

1. Add `user_id` field to `ExportToken` model
2. Update `Meta.indexes` to include composite index
3. Add `Meta.constraints` for unique constraint
4. Update `create_token()` classmethod:
   ```python
   @classmethod
   def create_token(cls, resource_type, resource_id, user_id):
       """Create a new export token for a user-resource pair."""
       token = str(uuid.uuid4())
       return cls.objects.create(
           token=token,
           resource_type=resource_type,
           resource_id=resource_id,
           user_id=user_id
       )
   ```
5. Add `get_or_create_token()` classmethod:
   ```python
   @classmethod
   def get_or_create_token(cls, resource_type, resource_id, user_id):
       """Get existing token or create new one for user-resource pair."""
       token_obj, created = cls.objects.get_or_create(
           resource_type=resource_type,
           resource_id=resource_id,
           user_id=user_id,
           defaults={'token': str(uuid.uuid4())}
       )
       return token_obj, created
   ```

**Files**: Remove `export_token` field from:
- `apps/core/models/users.py` (line 86)
- `apps/project_management/models/projects.py` (line 80)
- `apps/project_management/models/sites.py` (line 76)

### Phase 3: GraphQL Mutations

**File**: `apps/export/graphql/mutations.py`

**Changes to `CreateExportToken.mutate()` (lines 103-174)**:

```python
@staticmethod
def mutate(root, info, resource_type, resource_id):
    user = info.context.user
    resource_type_str = resource_type.value

    # Check permissions (unchanged)
    if not can_manage_export_token(user, resource_type_str, resource_id):
        raise GraphQLError(
            "You do not have permission to create an export token for this resource"
        )

    # Verify resource exists (unchanged validation logic)
    model_map = {
        "USER": User,
        "PROJECT": Project,
        "SITE": Site,
    }
    model = model_map[resource_type_str]
    try:
        resource = model.objects.get(pk=resource_id)
    except model.DoesNotExist:
        raise GraphQLError(f"{resource_type} not found")

    # Get or create token for this user-resource pair
    token_obj, created = ExportToken.get_or_create_token(
        resource_type_str,
        resource_id,
        str(user.id)
    )

    return CreateExportToken(token=token_obj)
```

**Key changes**:
1. Remove lines 143-152 (checking `resource.export_token`)
2. Remove lines 154-171 (creating token and storing on resource)
3. Replace with single call to `get_or_create_token()` with `user.id`

**Changes to `DeleteExportToken.mutate()` (lines 184-219)**:

```python
@staticmethod
def mutate(root, info, token):
    user = info.context.user

    try:
        token_obj = ExportToken.objects.get(token=token)

        # Check permissions (unchanged)
        if not can_manage_export_token(
            user, token_obj.resource_type, token_obj.resource_id
        ):
            raise GraphQLError(
                "You do not have permission to delete this export token"
            )

        # Delete token (no need to clear resource.export_token)
        token_obj.delete()

        return DeleteExportToken(success=True)
    except ExportToken.DoesNotExist:
        raise GraphQLError("Export token not found")
```

**Key changes**:
1. Remove lines 198-212 (clearing `export_token` field on resource)
2. Keep only the permission check and token deletion

### Phase 4: GraphQL Queries

**File**: `apps/export/graphql/queries.py`

**Changes to `resolve_export_token()` (lines 37-72)**:

```python
@staticmethod
def resolve_export_token(root, info, resource_type, resource_id):
    user = info.context.user
    resource_type_str = resource_type.value

    # Check permissions (unchanged)
    if not can_manage_export_token(user, resource_type_str, resource_id):
        raise GraphQLError(
            "You do not have permission to view the export token for this resource"
        )

    try:
        token_obj = ExportToken.objects.get(
            resource_type=resource_type_str,
            resource_id=resource_id,
            user_id=str(user.id)  # NEW: filter by user_id
        )
        return token_obj
    except ExportToken.DoesNotExist:
        return None
```

**Key changes**:
1. Add `user_id=str(user.id)` to the query (line 61-63)
2. This ensures users only see their own tokens

### Phase 5: Signal Handlers

**File**: `apps/export/signals.py`

**Update all three existing handlers** (lines 27-84):

1. **User deletion** (lines 27-44):
   ```python
   @receiver(post_save, sender=User)
   def delete_user_export_tokens_on_soft_delete(sender, instance, **kwargs):
       if instance.deleted_at is not None:
           # Delete all tokens created by this user
           ExportToken.objects.filter(user_id=str(instance.id)).delete()
   ```
   - Remove lines 40-44 (clearing export_token field)

2. **Project deletion** (lines 47-64):
   ```python
   @receiver(post_save, sender=Project)
   def delete_project_export_tokens_on_soft_delete(sender, instance, **kwargs):
       if instance.deleted_at is not None:
           # Delete all tokens for this project
           ExportToken.objects.filter(
               resource_type="PROJECT",
               resource_id=str(instance.id)
           ).delete()
   ```
   - Remove lines 60-64 (clearing export_token field)

3. **Site deletion** (lines 67-84):
   ```python
   @receiver(post_save, sender=Site)
   def delete_site_export_tokens_on_soft_delete(sender, instance, **kwargs):
       if instance.deleted_at is not None:
           # Delete all tokens for this site
           ExportToken.objects.filter(
               resource_type="SITE",
               resource_id=str(instance.id)
           ).delete()
   ```
   - Remove lines 80-84 (clearing export_token field)

**Add new handler** for membership removal:

```python
from apps.project_management.models import Membership

@receiver(post_save, sender=Membership)
def delete_export_tokens_on_membership_removal(sender, instance, **kwargs):
    """
    Delete export tokens when user is removed from a project.
    This includes tokens for the project itself and all sites in the project.
    """
    if instance.deleted_at is not None and instance.membership_list.project:
        project = instance.membership_list.project
        user_id = str(instance.user.id)

        # Delete user's token for this project
        ExportToken.objects.filter(
            user_id=user_id,
            resource_type="PROJECT",
            resource_id=str(project.id)
        ).delete()

        # Delete user's tokens for all sites in this project
        site_ids = project.sites.values_list('id', flat=True)
        ExportToken.objects.filter(
            user_id=user_id,
            resource_type="SITE",
            resource_id__in=[str(sid) for sid in site_ids]
        ).delete()
```

### Phase 6: Views (No Changes Needed)

**File**: `apps/export/views.py`

The `_resolve_export_token()` function (lines 28-37) remains unchanged:
```python
def _resolve_export_token(token):
    try:
        export_token = ExportToken.objects.get(token=token)
        return export_token.resource_type, export_token.resource_id
    except ExportToken.DoesNotExist:
        raise Http404(f"Export token not found: {token}")
```

This still works because:
1. Token is still unique (primary key)
2. We still return `(resource_type, resource_id)`
3. The `user_id` field doesn't affect public token-based access
4. Could optionally return `user_id` for future audit logging

## Testing Strategy

### 1. Migration Testing

**Setup**:
1. Restore database from backup (before export_token fields added)
2. Run new migration
3. Verify schema:
   ```sql
   \d export_token
   -- Should show: token, resource_type, resource_id, user_id
   -- Should show indexes on both token and [user_id, resource_type, resource_id]
   ```

### 2. GraphQL Mutation Testing

**Test Cases**:

1. **Create token for USER resource**:
   ```graphql
   mutation {
     createExportToken(resourceType: USER, resourceId: "user-uuid") {
       token {
         token
         resourceType
         resourceId
       }
     }
   }
   ```
   - Verify token created in database with `user_id` set
   - Verify User model has NO `export_token` field

2. **Create token again (idempotency)**:
   - Call same mutation again
   - Verify same token returned
   - Verify only one row in database

3. **Different user, same resource**:
   - Login as different user
   - Create token for same resource
   - Verify different token created
   - Verify two rows in database (different user_id)

4. **Delete token**:
   ```graphql
   mutation {
     deleteExportToken(token: "uuid") {
       success
     }
   }
   ```
   - Verify token deleted from database
   - Verify no errors about missing resource fields

### 3. Query Testing

**Test Cases**:

1. **Query own token**:
   ```graphql
   query {
     exportToken(resourceType: USER, resourceId: "user-uuid") {
       token
       resourceType
       resourceId
     }
   }
   ```
   - Verify returns token for current user

2. **Query different user's token**:
   - User A creates token for resource
   - User B queries for token on same resource
   - Verify returns null (not User A's token)

### 4. Export URL Testing

**Test Cases**:

1. **User export (currently implemented)**:
   ```
   GET /export/token/user_all/{token}/filename.csv
   ```
   - Verify CSV exports correctly
   - Verify permissions enforced via token

2. **Future: Project export** (not yet implemented):
   - Verify works when implemented

3. **Future: Site export** (not yet implemented):
   - Verify works when implemented

### 5. Cleanup Testing

**Test Cases**:

1. **User soft deletion**:
   - User creates tokens for themselves
   - Soft delete user
   - Verify all tokens with `user_id=user.id` deleted

2. **Project soft deletion**:
   - Multiple users create tokens for same project
   - Soft delete project
   - Verify all tokens for that project deleted (all users)

3. **Site soft deletion**:
   - Multiple users create tokens for same site
   - Soft delete site
   - Verify all tokens for that site deleted (all users)

4. **Membership removal** (NEW):
   - User is member of project with sites
   - User creates tokens for project and sites
   - Remove user from project
   - Verify tokens deleted for:
     - That project
     - All sites in that project
   - Verify tokens NOT deleted for:
     - Other projects user is in
     - User's own unaffiliated sites

## Migration File Details

### New Migration: `0002_redesign_export_token.py`

This migration replaces the need for:
- `apps/core/migrations/0053_add_export_token_to_user.py`
- `apps/project_management/migrations/0029_alter_projectsettings_options.py` (drift)
- `apps/project_management/migrations/0030_add_export_token_to_project_and_site.py`

**Operations**:

```python
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('export', '0001_create_export_token'),
    ]

    operations = [
        # Add user_id field to ExportToken
        migrations.AddField(
            model_name='exporttoken',
            name='user_id',
            field=models.CharField(max_length=255),
        ),

        # Add composite index
        migrations.AddIndex(
            model_name='exporttoken',
            index=models.Index(
                fields=['user_id', 'resource_type', 'resource_id'],
                name='export_token_user_resource_idx'
            ),
        ),

        # Add unique constraint
        migrations.AddConstraint(
            model_name='exporttoken',
            constraint=models.UniqueConstraint(
                fields=['user_id', 'resource_type', 'resource_id'],
                name='unique_user_resource_token'
            ),
        ),
    ]
```

**Note**: Since we're starting from a clean database (before 0053, 0029, 0030), we don't need to:
- Remove export_token fields (they were never added)
- Migrate existing data (there is none)

## Summary of Changes

### Files to Modify

1. **apps/export/models.py**:
   - Add `user_id` field
   - Update indexes and constraints
   - Update `create_token()` method signature
   - Add `get_or_create_token()` method

2. **apps/export/graphql/mutations.py**:
   - Simplify `CreateExportToken.mutate()` (remove resource field updates)
   - Simplify `DeleteExportToken.mutate()` (remove resource field clearing)

3. **apps/export/graphql/queries.py**:
   - Add `user_id` filter to `resolve_export_token()`

4. **apps/export/signals.py**:
   - Simplify all three existing handlers (remove field clearing)
   - Add new handler for membership removal

5. **apps/core/models/users.py**:
   - Remove `export_token` field (line 86)

6. **apps/project_management/models/projects.py**:
   - Remove `export_token` field (line 80)

7. **apps/project_management/models/sites.py**:
   - Remove `export_token` field (line 76)

### Files to Create

1. **apps/export/migrations/0002_redesign_export_token.py**:
   - Add user_id field
   - Add composite index
   - Add unique constraint

### Files Unchanged

1. **apps/export/views.py**: No changes needed
2. **apps/export/handlers.py**: No changes needed (CORS config)
3. **apps/export/transformers.py**: No changes needed (data transformation)
4. **apps/export/formatters.py**: No changes needed (CSV generation)
5. **apps/export/fetch_data.py**: No changes needed (GraphQL data fetching)
6. **apps/export/fetch_lists.py**: No changes needed (list fetching)

## Benefits of New Architecture

1. **Multi-user support**: Multiple users can have tokens for the same resource
2. **User-scoped tokens**: Each user sees only their own tokens
3. **Better cleanup**: User deletion removes all their tokens automatically
4. **Simpler model**: Resource models don't need export_token field
5. **Proper cascading**: Membership removal properly cleans up tokens
6. **Audit trail**: `user_id` on token enables future audit logging
7. **Single source of truth**: All token data in one table with proper indexes

## Risks and Mitigations

### Risk 1: Breaking Changes for Existing Tokens

**Mitigation**: Since migrations 0053/0030 haven't been applied to production, we're starting from a clean state. No existing tokens to migrate.

### Risk 2: Performance with Multiple Tokens

**Mitigation**: Composite index on `[user_id, resource_type, resource_id]` ensures fast lookups. Token lookups remain fast via primary key.

### Risk 3: Membership Removal Signal

**Mitigation**: Thoroughly test signal triggers. Ensure we're detecting the correct deletion pattern (soft delete vs hard delete).

## Future Enhancements

1. **Audit Logging**: Use `user_id` from token to log which user's export was accessed
2. **Token Expiration**: Add `created_at` and `expires_at` fields for time-limited tokens
3. **Token Analytics**: Track export usage by user and resource
4. **Batch Operations**: Add GraphQL mutations for managing multiple tokens at once
