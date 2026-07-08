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

"""Diagnostic: list the rows that would block a User soft-delete.

The runtime gate (`User.delete`) refuses soft-delete when the user has
undeletable data but doesn't surface which rows. Support / engineers
run this command to see specifics before manually cleaning up.

Usage (from repo root):
    make show-deletion-blockers user=foo@example.com
    make show-deletion-blockers user=<user-uuid>

Or directly:
    python manage.py show_deletion_blockers foo@example.com
    python manage.py show_deletion_blockers <user-uuid>
"""

import structlog
from django.contrib.admin.utils import NestedObjects
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import router

from apps.core.models import User

logger = structlog.get_logger(__name__)

# Cap pk strings attached to each blocker so this stays readable for
# users with a large footprint. `count` is always the true total.
BLOCKER_ID_CAP = 50


class Command(BaseCommand):
    help = "Show rows that would block soft-delete for a User."

    def add_arguments(self, parser):
        parser.add_argument("user", help="Email or ID of the user to inspect")

    def handle(self, *args, **options):
        user = _find_user(options["user"])
        blockers = deletion_blockers(user)
        if not blockers:
            self.stdout.write(f"No deletion blockers for {user.email!r}.")
            return
        self.stdout.write(f"Deletion blockers for {user.email!r}:")
        for b in blockers:
            label, detail = format_blocker(b)
            self.stdout.write(f"  - {label}: {detail}")


def _find_user(identifier):
    if "@" in identifier:
        try:
            return User.objects.get(email=identifier)
        except User.DoesNotExist:
            raise CommandError(f"No user with email {identifier!r}")
    try:
        return User.objects.get(id=identifier)
    except (User.DoesNotExist, ValidationError):
        raise CommandError(f"No user with ID {identifier!r}")


def deletion_blockers(user):
    """Return blocker dicts matching what `User.delete()` would refuse on.

    Two sources — the same two the gate checks:

      1. PROTECT/RESTRICT rows — Django's `NestedObjects` collector
         reports these in `.protected`. safedelete's SOFT_DELETE_CASCADE
         raises `ProtectedError` from the same collector output, so this
         side stays in lock-step with the runtime gate by construction
         (no separate FK-classification logic to drift).

      2. Non-project APPROVED Memberships — `Membership.user` is CASCADE
         at the DB layer so the collector doesn't flag them, but the
         gate refuses them as a policy blocker. We call the same method
         (`User._non_project_approved_memberships`) the gate uses.

    Only active rows count: `.protected` includes soft-deleted rows, so
    we filter by `deleted_at IS NULL` just like safedelete does before
    raising. Soft-deleted rows are handled by the harddelete cron.

    Each blocker is `{model, qualifier, field, count, ids}` where
    `qualifier` is Optional[str] (None for FK blockers, populated for
    the Membership policy override) and `ids` is up to BLOCKER_ID_CAP
    pk strings; `count` is the true total.
    """
    blockers = _collect_fk_blockers(user)

    # Policy blocker safedelete can't see (Membership.user is CASCADE).
    memberships = user._non_project_approved_memberships()
    memb_count = memberships.count()
    if memb_count > 0:
        blockers.append(
            {
                "model": "collaboration.Membership",
                "qualifier": "non-project, approved",
                "field": "user",
                "count": memb_count,
                "ids": [
                    str(pk) for pk in memberships.values_list("pk", flat=True)[:BLOCKER_ID_CAP]
                ],
            }
        )
    return blockers


def _collect_fk_blockers(user):
    """PROTECT/RESTRICT rows reachable from the user, sourced from the
    same Django collector safedelete raises from.

    Grouped by (model, field) so the output shape matches the Membership
    entry — one dict per blocker kind, with pk strings capped."""
    collector = NestedObjects(using=router.db_for_write(type(user)))
    collector.collect([user])

    active_protected = [
        obj for obj in collector.protected if getattr(obj, "deleted_at", None) is None
    ]

    by_key = {}
    for obj in active_protected:
        field = _find_fk_to_user(obj, user)
        by_key.setdefault((obj._meta.label, field), []).append(obj)

    return [
        {
            "model": model_label,
            "qualifier": None,
            "field": field_name,
            "count": len(objs),
            "ids": [str(o.pk) for o in objs[:BLOCKER_ID_CAP]],
        }
        for (model_label, field_name), objs in sorted(by_key.items())
    ]


def _find_fk_to_user(obj, user):
    """Return the name of the FK on `obj` that points at `user`.

    Every model this codebase reaches via `.protected` from a User has
    exactly one such FK (typically `created_by`). Iterate concrete FK
    fields and match by referenced pk to avoid a DB fetch."""
    for f in obj._meta.concrete_fields:
        if f.is_relation and f.related_model is type(user):
            if getattr(obj, f.attname, None) == user.pk:
                return f.name
    # Reachable only if a future model shows up in `.protected` without a
    # direct concrete FK to User. Log so the surprise surfaces in Sentry
    # instead of silently rendering as `(?)` in the diagnostic output.
    logger.warning(
        "show_deletion_blockers.fk_not_found",
        model=obj._meta.label,
        pk=str(obj.pk),
        user_id=str(user.pk),
    )
    return "?"


def format_blocker(b):
    """Render one blocker dict as "<label>: <detail>". Truncated `ids`
    show with "(+N more)"."""
    qualifier = f" ({b['qualifier']})" if b.get("qualifier") else ""
    label = f"{b['model']}{qualifier} ({b['field']})"
    ids = b.get("ids") or []
    extra = b["count"] - len(ids)
    if not ids:
        detail = f"{b['count']} row(s)"
    elif extra > 0:
        detail = f"{b['count']} row(s); first {len(ids)} IDs: {', '.join(ids)} (+{extra} more)"
    else:
        detail = f"{b['count']} row(s); IDs: {', '.join(ids)}"
    return label, detail
