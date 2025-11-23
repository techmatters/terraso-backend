# Migration Commit Plan

## Summary of Migrations

### Drift Migrations (fix/drift_migrations branch)

These migrations capture model changes that were applied to production but never recorded in migrations. They use `SeparateDatabaseAndState` to update Django's migration state without changing the database (since production already has these changes).

#### 1. `story_map/0007_alter_storymap_title.py`
**What it does:**
- Adds `validate_name` validator to `StoryMap.title` field
- **State-only change** - validators don't affect database schema
- Production already has this validator in the model code, this just records it in migrations

**Key changes:**
- `StoryMap.title` now has `validators=[apps.core.models.commons.validate_name]`

#### 2. `shared_data/0019_alter_dataentry_created_by_and_more.py`
**What it does:**
- Adds `db_index=True` to `deleted_at` fields on `DataEntry` and `VisualizationConfig`
- Changes `DataEntry.created_by` ForeignKey `on_delete` to `DO_NOTHING`
- **State-only change** - production database already has these changes from 2022

**Key changes:**
- `DataEntry.deleted_at`: Added index for performance
- `VisualizationConfig.deleted_at`: Added index for performance
- `DataEntry.created_by`: Changed to `on_delete=DO_NOTHING`

#### 3. `core/0052_landscapedefaultgroup_and_more.py`
**What it does:**
- Large drift migration capturing multiple changes from django-safedelete 1.3.0 upgrade (Sept 2022)
- Adds `db_index=True` to multiple `deleted_at` fields
- Updates field choices to match current production
- Creates `LandscapeDefaultGroup` proxy model
- Conditionally creates `BackgroundTask` table if needed

**Key changes:**
- Creates `LandscapeDefaultGroup` proxy model
- Adds indexes to `deleted_at` on: `Group`, `GroupAssociation`, `Landscape`, `LandscapeGroup`, `Membership`, `User`
- Updates `Landscape.partnership_status` choices
- Updates `Membership.user_role` choices
- Updates `TaxonomyTerm.type` choices
- Updates `SharedResource.share_access` choices
- Adds validator to `TaxonomyTerm.value_original`
- Conditionally creates `BackgroundTask` table

#### 4. `project_management/0029_alter_projectsettings_options.py`
**What it does:**
- Updates Meta options for `ProjectSettings` model
- **State-only change** - Meta options don't affect database schema

**Key changes:**
- Sets `ProjectSettings` Meta options:
  - `get_latest_by = '-created_at'`
  - `ordering = ['created_at']`
  - `verbose_name_plural = 'project settings'`

### Export Token Migrations (feat/export branch)

These migrations implement the export token feature that will later be redesigned.

#### 1. `export/0001_create_export_token.py`
**What it does:**
- Creates initial `ExportToken` model and table
- This is the base export token implementation

**Key changes:**
- Creates `export_token` table with fields:
  - `token` (CharField, primary key, max_length=36)
  - `resource_type` (CharField with choices: USER, PROJECT, SITE)
  - `resource_id` (CharField, max_length=255)
- Adds composite index on `[resource_type, resource_id]`

#### 2. `project_management/0030_add_export_token_to_project_and_site.py`
**What it does:**
- Adds `export_token` field to `Project` and `Site` models
- Part of the original export token design (will be removed in redesign)

**Key changes:**
- `Project.export_token`: CharField(max_length=36, null=True, blank=True, unique=True)
- `Site.export_token`: CharField(max_length=36, null=True, blank=True, unique=True)

#### 3. `core/0053_add_export_token_to_user.py`
**What it does:**
- Adds `export_token` field to `User` model
- Part of the original export token design (will be removed in redesign)

**Key changes:**
- `User.export_token`: CharField(max_length=36, null=True, blank=True, unique=True)

## Git Workflow Plan

### Current State
- Branch: `feat/export`
- Uncommitted changes:
  - Modified export app files (transformers, views, mutations, queries, etc.)
  - New files (EXPORT_TOKEN_REDESIGN_PLAN.md, handlers.py, scripts, etc.)
  - Migration files exist but not committed

### Proposed Workflow

#### Option A: Drift First, Then Export Feature (Recommended)

This approach keeps drift fixes separate and makes them easier to merge to main independently.

```bash
# 1. Create drift migrations branch from main
git checkout main
git pull origin main
git checkout -b fix/drift_migrations

# 2. Add and commit ONLY drift migrations
git add terraso_backend/apps/story_map/migrations/0007_alter_storymap_title.py
git add terraso_backend/apps/shared_data/migrations/0019_alter_dataentry_created_by_and_more.py
git add terraso_backend/apps/core/migrations/0052_landscapedefaultgroup_and_more.py
git add terraso_backend/apps/project_management/migrations/0029_alter_projectsettings_options.py

git commit -m "fix: Add drift migrations for model changes since 2022

Captures model changes that were applied to production but never
recorded in migrations:

- story_map/0007: Add validate_name validator to StoryMap.title
- shared_data/0019: Add db_index to deleted_at fields, update ForeignKey
- core/0052: Multiple changes from django-safedelete 1.3.0 upgrade
- project_management/0029: Update ProjectSettings Meta options

All migrations use SeparateDatabaseAndState to update Django's migration
state without changing the database (production already has these changes).

IMPORTANT: These migrations are irreversible to prevent accidental
production breakage."

# 3. Push drift migrations branch
git push -u origin fix/drift_migrations

# 4. Go back to export feature branch
git checkout feat/export

# 5. Rebase export feature on top of drift migrations
git rebase fix/drift_migrations

# 6. Add and commit export token migrations
git add terraso_backend/apps/export/migrations/0001_create_export_token.py
git add terraso_backend/apps/project_management/migrations/0030_add_export_token_to_project_and_site.py
git add terraso_backend/apps/core/migrations/0053_add_export_token_to_user.py

git commit -m "feat: Add export token migrations (original design)

Creates ExportToken model and adds export_token fields to User,
Project, and Site models.

NOTE: This design will be superseded by the redesign in
EXPORT_TOKEN_REDESIGN_PLAN.md which removes export_token fields
from resource models and adds user_id to ExportToken table."

# 7. Add and commit all other export changes
git add terraso_backend/apps/export/
git add terraso_backend/config/settings.py
git add restore_from_render.sh
# ... etc

git commit -m "feat: Implement export functionality with CSV/JSON support

- Add export transformers for soil data
- Add GraphQL mutations and queries for export tokens
- Add export views for token-based and ID-based exports
- Add CORS handler for public export URLs
- Add implementation plan for export token redesign
- Add database restore script"

# 8. Push export feature branch
git push -u origin feat/export --force-with-lease
```

#### Option B: All in One Branch

```bash
# 1. Stay on feat/export branch
# Current branch: feat/export

# 2. Commit drift migrations first
git add terraso_backend/apps/story_map/migrations/0007_alter_storymap_title.py
git add terraso_backend/apps/shared_data/migrations/0019_alter_dataentry_created_by_and_more.py
git add terraso_backend/apps/core/migrations/0052_landscapedefaultgroup_and_more.py
git add terraso_backend/apps/project_management/migrations/0029_alter_projectsettings_options.py

git commit -m "fix: Add drift migrations for model changes since 2022"

# 3. Commit export token migrations
git add terraso_backend/apps/export/migrations/0001_create_export_token.py
git add terraso_backend/apps/project_management/migrations/0030_add_export_token_to_project_and_site.py
git add terraso_backend/apps/core/migrations/0053_add_export_token_to_user.py

git commit -m "feat: Add export token migrations (original design)"

# 4. Commit all other changes
git add .
git commit -m "feat: Implement export functionality with CSV/JSON support"

# 5. Push
git push -u origin feat/export
```

### Recommendation

**Use Option A** because:
1. Drift migrations can be merged to main independently
2. Clearer separation of concerns
3. Easier to review drift fixes separately from new features
4. If export redesign takes time, drift fixes can go out first
5. Better git history for future reference

### Migration Dependencies

After Option A, the migration dependency chain will be:

```
main:
  └─ core/0051_*
      └─ core/0052_* (drift) ← fix/drift_migrations branch
          └─ core/0053_* (export_token field) ← feat/export branch

  └─ project_management/0028_*
      └─ project_management/0029_* (drift) ← fix/drift_migrations branch
          └─ project_management/0030_* (export_token fields) ← feat/export branch

  └─ story_map/0006_*
      └─ story_map/0007_* (drift) ← fix/drift_migrations branch

  └─ shared_data/0018_*
      └─ shared_data/0019_* (drift) ← fix/drift_migrations branch

export (new app):
  └─ export/0001_* (create ExportToken table) ← feat/export branch
```

### Testing After Rebase

After rebasing feat/export on fix/drift_migrations:

```bash
# 1. Restore database from backup
./restore_from_render.sh

# 2. Run migrations
python terraso_backend/manage.py migrate

# 3. Verify migration order
python terraso_backend/manage.py showmigrations

# Expected output should show:
# core
#   ...
#   [X] 0051_*
#   [X] 0052_landscapedefaultgroup_and_more (drift)
#   [X] 0053_add_export_token_to_user (export)
#
# project_management
#   ...
#   [X] 0028_*
#   [X] 0029_alter_projectsettings_options (drift)
#   [X] 0030_add_export_token_to_project_and_site (export)
#
# story_map
#   ...
#   [X] 0006_*
#   [X] 0007_alter_storymap_title (drift)
#
# shared_data
#   ...
#   [X] 0018_*
#   [X] 0019_alter_dataentry_created_by_and_more (drift)
#
# export
#   [X] 0001_create_export_token (export)
```

### Notes

1. **Do NOT run migrations on production** until the drift migrations are merged to main and deployed first
2. The drift migrations must go out before the export token migrations
3. Both fix/drift_migrations and feat/export branches should pass CI tests
4. Consider creating a PR for fix/drift_migrations first, get it reviewed and merged, then create PR for feat/export
