# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Terraso Backend is a Django-based GraphQL API that powers a collaborative platform for landscape/environmental management with specialized soil research capabilities. It supports field research teams with data collection, visualization, and sharing features.

## Development Commands

### Docker-based Development (Recommended)
- `make build` - Build Docker images
- `make run` - Start the development server
- `make migrate` - Run database migrations
- `make bash` - Access the web container shell
- `make connect_db` - Connect to PostgreSQL database

### Testing
- `make test` - Run all tests (unit + integration)
- `make test_unit` - Run unit tests only
- `make test_integration` - Run integration tests only
- `PATTERN="test_name" make test_unit` - Run specific test pattern

### Code Quality
- `make lint` - Run ruff linting and format checks
- `make format` - Format code with ruff
- `make check_api_schema` - Verify GraphQL schema consistency

### Dependencies
- `make lock` - Lock production dependencies to requirements.txt
- `make lock-dev` - Lock development dependencies
- `make install` - Install production dependencies
- `make install-dev` - Install development dependencies

### Database Management
- `APP_MIGRATION_NAME="app_name migration_number" make migrate` - Run specific migration
- `APP_MIGRATION_NAME="app_name migration_name" make print_migration_sql` - View migration SQL
- `make makemigrations` - Create new migrations
- `make showmigrations` - Show migration status

### Other Commands
- `make setup-git-hooks` - Install pre-commit hooks
- `make api_docs` - Generate GraphQL API documentation
- `make download-soil-data` - Download required soil ID data files

## Architecture Overview

### Django Apps Structure

**Core Infrastructure:**
- `core` - User management, groups, landscapes, permissions, and shared utilities
- `auth` - JWT authentication, OAuth2 (Google/Apple/Microsoft), custom middleware
- `graphql` - Centralized GraphQL API using Graphene-Django with Relay patterns
- `collaboration` - Generic membership/role framework for groups, landscapes, projects

**Domain Features:**
- `project_management` - Research projects, field sites, site notes
- `soil_id` - Specialized soil data with depth intervals and project-specific settings
- `shared_data` - Data entries and visualization configurations
- `story_map` - Collaborative story maps with media uploads
- `storage` - S3 file uploads for various media types
- `notifications` - Email notification system
- `export` - Data export functionality for sites and projects (CSV, JSON formats)

### GraphQL API Design

- **Relay-style connections** for pagination
- **Custom base classes**: `TerrasoRelayNode`, `BaseWriteMutation`, `BaseDeleteMutation`
- **Modular schema** with each app contributing types and mutations
- **Centralized schema** at `terraso_backend/apps/graphql/schema/schema.py`
- Schema auto-generation: `make api_schema`

### Authentication & Authorization

- **JWT tokens** with custom middleware (`JWTAuthenticationMiddleware`)
- **OAuth2/OIDC** for external service integrations
- **Multiple OAuth providers**: Google (Android/iOS), Apple, Microsoft
- **Rule-based permissions** using `django-rules` for fine-grained access control
- **Role-based collaboration** (manager/member roles)
- **Soft deletion** with `django-safedelete` and cascade policies

### Data Model Patterns

- **UUID primary keys** across all models
- **Soft deletion** with `deleted_at` timestamps and recovery capabilities
- **Audit trails** with `created_at`/`updated_at` fields
- **Generic collaboration** through membership system
- **Multi-database support** (separate soil data database)

### Key Integrations

- **AWS S3** for file storage
- **AWS SES** for email delivery
- **Mapbox** for geospatial services
- **HubSpot** for CRM integration
- **Sentry** for error monitoring
- **Airtable** for external data integration

## Code Conventions

### Python/Django
- Follow existing patterns in each app
- Use `django-rules` for permissions (see `core.permission_rules`)
- Implement soft deletion with appropriate policies
- Use UUID primary keys for new models
- Follow the established GraphQL patterns with base classes

### Dependencies
- Check existing `requirements.txt` for available libraries
- Use `uv pip compile` for dependency management (not pip-tools)
- GDAL and Cython required for local development

### Testing
- Unit tests marked with `pytest.mark.unit` (default)
- Integration tests marked with `pytest.mark.integration`
- Tests automatically compile translations and run without cache in CI

### Pre-commit Hooks
- Ruff linting and formatting
- Conventional commit messages
- GraphQL schema consistency checks
- Install with `make setup-git-hooks`

## Environment Setup

1. Copy `.env.sample` to `.env`
2. Configure OAuth credentials for Google, Apple, Microsoft
3. Run `make build` to build Docker images
4. Run `make migrate` for initial database setup
5. Use `make run` to start development server

## Soil Data Special Requirements

The soil_id app requires external data files downloaded with `make download-soil-data`. These files are stored in Google Drive and needed for soil identification algorithms.