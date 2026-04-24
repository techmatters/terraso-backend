# Copyright © 2026 Technology Matters
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see https://www.gnu.org/licenses/.

import enum
import uuid

import graphene
import structlog
from django.db import IntegrityError, transaction
from django.forms import ValidationError

from apps.core.models import User
from apps.graphql.schema.commons import BaseWriteMutation
from apps.graphql.schema.sites import SiteNode
from apps.project_management.models.projects import Project
from apps.project_management.models.site_notes import SiteNote
from apps.project_management.models.site_push_history import SitePushHistory
from apps.project_management.models.sites import Site
from apps.project_management.permission_rules import Context
from apps.project_management.permission_table import (
    ProjectAction,
    SiteAction,
    check_project_permission,
    check_site_permission,
)
from apps.soil_id.models import SoilData, SoilMetadata

logger = structlog.get_logger(__name__)


class SitePushNoteInput(graphene.InputObjectType):
    id = graphene.ID(required=True)
    content = graphene.String(required=True)


class SitePushInputEntry(graphene.InputObjectType):
    site_id = graphene.ID(required=True)
    is_new = graphene.Boolean(required=True)
    # Site-level fields — required for new sites, optional for updates
    name = graphene.String()
    latitude = graphene.Float()
    longitude = graphene.Float()
    elevation = graphene.Float()
    privacy = SiteNode.privacy_enum()
    project_id = graphene.ID()
    # Note operations
    new_notes = graphene.List(graphene.NonNull(SitePushNoteInput), required=True)
    updated_notes = graphene.List(graphene.NonNull(SitePushNoteInput), required=True)
    deleted_note_ids = graphene.List(graphene.NonNull(graphene.ID), required=True)


class SitePushFailureReason(graphene.Enum):
    SITE_DOES_NOT_EXIST = "SITE_DOES_NOT_EXIST"
    NOT_ALLOWED = "NOT_ALLOWED"
    INVALID_DATA = "INVALID_DATA"
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"


class SitePushEntrySuccess(graphene.ObjectType):
    site = graphene.Field(SiteNode, required=True)


class SitePushEntryFailure(graphene.ObjectType):
    reason = graphene.Field(SitePushFailureReason, required=True)


class SitePushEntryResult(graphene.Union):
    class Meta:
        types = (SitePushEntrySuccess, SitePushEntryFailure)


class SitePushEntry(graphene.ObjectType):
    site_id = graphene.ID(required=True)
    result = graphene.Field(SitePushEntryResult, required=True)


# NOTE: we catch errors at the granularity of each site in the request.
#       So one site's updates can succeed while another fails. But if any of
#       an individual site's updates are invalid (including note conflicts), we
#       reject all of that site's updates atomically.
class SitePush(BaseWriteMutation):
    """
    Not exposed as a standalone mutation — only callable through UserDataPush.
    Handles bulk site sync: creates/updates sites and their notes with per-site atomicity.
    """

    results = graphene.Field(graphene.List(graphene.NonNull(SitePushEntry)), required=True)

    class Input:
        site_entries = graphene.Field(
            graphene.List(graphene.NonNull(SitePushInputEntry)), required=True
        )

    class SiteConflictError(Exception):
        """Raised for sync conflict conditions (not found, not allowed) within a site entry."""

        def __init__(self, reason: SitePushFailureReason):
            self.reason = reason

    @staticmethod
    def log_site_push(user: User, site_entries: list[dict]) -> list[SitePushHistory]:
        history_entries = []
        for entry in site_entries:
            site_id = entry.get("site_id")
            site = Site.objects.filter(id=site_id).first() if site_id else None
            history_entry = SitePushHistory(
                site=site,
                changed_by=user,
                site_changes={
                    "is_new": entry.get("is_new"),
                    "name": entry.get("name"),
                    "latitude": entry.get("latitude"),
                    "longitude": entry.get("longitude"),
                    "elevation": entry.get("elevation"),
                    "privacy": entry.get("privacy"),
                    "project_id": entry.get("project_id"),
                    "new_notes": entry.get("new_notes", []),
                    "updated_notes": entry.get("updated_notes", []),
                    "deleted_note_ids": entry.get("deleted_note_ids", []),
                },
            )
            history_entry.save()
            history_entries.append(history_entry)
        return history_entries

    @staticmethod
    def log_failure(history_entry: SitePushHistory, reason: SitePushFailureReason):
        history_entry.update_failure_reason = reason.value
        history_entry.save()

    @staticmethod
    def _process_site_entry(user: User, site_entry: dict) -> Site:
        """
        Performs all DB writes for a single site entry.
        Raises SitePush.SiteConflictError for conflict conditions (not found, not allowed).
        Raises ValidationError/IntegrityError for invalid data.
        All writes happen within the caller's transaction.atomic() savepoint.
        """
        site_id = site_entry["site_id"]
        is_new = site_entry["is_new"]

        # --- Site-level operation ---
        if is_new:
            # Adding a new site
            try:
                site_uuid = uuid.UUID(str(site_id))
            except ValueError:
                raise SitePush.SiteConflictError(SitePushFailureReason.INVALID_DATA)

            # Idempotent: if UUID already exists, return existing site without error
            existing = Site.objects.filter(id=site_uuid).first()
            if existing:
                site = existing
            else:
                site_kwargs = {
                    "name": site_entry["name"],
                    "latitude": site_entry["latitude"],
                    "longitude": site_entry["longitude"],
                }
                if site_entry.get("elevation") is not None:
                    site_kwargs["elevation"] = site_entry["elevation"]
                if site_entry.get("privacy"):
                    privacy_val = site_entry["privacy"]
                    site_kwargs["privacy"] = (
                        privacy_val.value if isinstance(privacy_val, enum.Enum) else privacy_val
                    )

                # Handle project affiliation — silently make site unaffiliated (drop the project value) if project not found/no permission
                project_id = site_entry.get("project_id")
                project = Project.objects.filter(id=project_id).first() if project_id else None
                if project and check_project_permission(
                    user, ProjectAction.ADD_NEW_SITE, Context(project=project)
                ):
                    site_kwargs["project"] = project
                else:
                    site_kwargs["owner"] = user

                site = Site(id=site_uuid, **site_kwargs)
                site.save()
                SoilData.objects.create(site=site)
                SoilMetadata.objects.create(site=site)
                site.mark_seen_by(user)
        else:
            # Updating an existing site
            site = Site.objects.filter(id=site_id).first()
            if site is None:
                raise SitePush.SiteConflictError(SitePushFailureReason.SITE_DOES_NOT_EXIST)

            # Lightweight access check: the user must have *some* relationship
            # to the site (they own it, or they're a member of its project).
            # Without this, a completely unauthorized user would get a silent
            # success with all operations skipped — technically harmless (no
            # data changes) but misleading, and it would mask misconfigurations
            # or stale client state.
            is_accessible = site.owner == user or (site.project and site.project.is_member(user))
            if not is_accessible:
                raise SitePush.SiteConflictError(SitePushFailureReason.NOT_ALLOWED)

            # --- Site-level field updates (best-effort) ---
            # Field updates require UPDATE_SETTINGS permission (manager-only
            # for affiliated sites). If the user doesn't have it, we skip the
            # field updates rather than rejecting the entire entry — the user
            # may still have permission for note operations below.
            field_updates = {}
            for field in ["name", "latitude", "longitude", "elevation", "privacy"]:
                val = site_entry.get(field)
                if val is not None:
                    field_updates[field] = val.value if isinstance(val, enum.Enum) else val

            has_project_update = site_entry.get("project_id") is not None

            if field_updates or has_project_update:
                if check_site_permission(user, SiteAction.UPDATE_SETTINGS, Context(site=site)):
                    if has_project_update:
                        project = Project.objects.filter(id=site_entry["project_id"]).first()
                        if project:
                            site.add_to_project(project)

                    if field_updates:
                        for k, v in field_updates.items():
                            setattr(site, k, v)
                        site.save()
                else:
                    # Elevation is a special case: contributors can set it if
                    # currently null, but not overwrite an existing value
                    # (that's a settings change). This is needed because
                    # elevation data comes from an external API
                    # (epqs.nationalmap.gov) that isn't available while
                    # offline. A site created offline will have null elevation;
                    # once the device is back online and the elevation lookup
                    # succeeds, the client pushes the value. Contributors need
                    # to be able to fill this in without manager permissions.
                    elevation_val = field_updates.get("elevation")
                    if elevation_val is not None and site.elevation is None:
                        site.elevation = elevation_val
                        site.save()
                    logger.info(
                        "site_push.skipped_field_updates",
                        site_id=str(site_id),
                        user_id=str(user.id),
                        reason="not_allowed",
                    )

        # --- Note operations (best-effort per note) ---
        # Each note operation is checked individually. If the user lacks
        # permission for a specific note (e.g. editing someone else's note),
        # that note is skipped rather than rejecting the entire entry.
        for note_input in site_entry.get("new_notes", []):
            note_id_str = note_input["id"]
            try:
                note_uuid = uuid.UUID(str(note_id_str))
            except ValueError:
                raise SitePush.SiteConflictError(SitePushFailureReason.INVALID_DATA)

            # Idempotent: if note UUID already exists, skip without error
            if SiteNote.objects.filter(id=note_uuid).exists():
                continue

            if not check_site_permission(user, SiteAction.CREATE_NOTE, Context(site=site)):
                logger.info(
                    "site_push.skipped_create_note",
                    site_id=str(site_id),
                    note_id=note_id_str,
                    user_id=str(user.id),
                    reason="not_allowed",
                )
                continue

            SiteNote.objects.create(
                id=note_uuid, site=site, content=note_input["content"], author=user
            )

        for note_input in site_entry.get("updated_notes", []):
            note = SiteNote.objects.filter(id=note_input["id"]).first()
            if note is None:
                continue  # Idempotent: note was deleted externally, skip update

            if not check_site_permission(user, SiteAction.EDIT_NOTE, Context(site_note=note)):
                logger.info(
                    "site_push.skipped_edit_note",
                    site_id=str(site_id),
                    note_id=str(note_input["id"]),
                    user_id=str(user.id),
                    reason="not_allowed",
                )
                continue

            note.content = note_input["content"]
            note.save()

        for note_id_str in site_entry.get("deleted_note_ids", []):
            note = SiteNote.objects.filter(id=note_id_str).first()
            if note is None:
                continue  # Idempotent: already deleted is a success

            if not check_site_permission(user, SiteAction.DELETE_NOTE, Context(site_note=note)):
                logger.info(
                    "site_push.skipped_delete_note",
                    site_id=str(site_id),
                    note_id=note_id_str,
                    user_id=str(user.id),
                    reason="not_allowed",
                )
                continue

            note.delete()

        # Refresh to capture any server-side changes (e.g. updated_at, related notes)
        site.refresh_from_db()
        return site

    @staticmethod
    def mutate_and_get_entry_result(
        user: User, site_entry: dict, history_entry: SitePushHistory
    ) -> SitePushEntry:
        site_id = site_entry["site_id"]
        try:
            with transaction.atomic():
                site = SitePush._process_site_entry(user, site_entry)
                history_entry.update_succeeded = True
                history_entry.save()
                return SitePushEntry(site_id=site_id, result=SitePushEntrySuccess(site=site))
        except SitePush.SiteConflictError as e:
            SitePush.log_failure(history_entry, e.reason)
            return SitePushEntry(site_id=site_id, result=SitePushEntryFailure(reason=e.reason))
        except (ValidationError, IntegrityError) as e:
            logger.warning("site_push.invalid_data", site_id=site_id, error=str(e))
            SitePush.log_failure(history_entry, SitePushFailureReason.INVALID_DATA)
            return SitePushEntry(
                site_id=site_id,
                result=SitePushEntryFailure(reason=SitePushFailureReason.INVALID_DATA),
            )
        except Exception as e:
            logger.warning("site_push.unexpected_error", site_id=site_id, error=str(e))
            SitePush.log_failure(history_entry, SitePushFailureReason.UNEXPECTED_ERROR)
            return SitePushEntry(
                site_id=site_id,
                result=SitePushEntryFailure(reason=SitePushFailureReason.UNEXPECTED_ERROR),
            )

    @classmethod
    def mutate_and_get_payload(cls, root, info, site_entries: list[dict]):
        user = info.context.user

        # Log all incoming entries atomically before processing
        with transaction.atomic():
            history_entries = SitePush.log_site_push(user, site_entries)

        results = [
            SitePush.mutate_and_get_entry_result(
                user=user, site_entry=entry, history_entry=history_entry
            )
            for entry, history_entry in zip(site_entries, history_entries)
        ]
        return cls(results=results)
