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

Usage:
    python manage.py show_deletion_blockers foo@example.com
    python manage.py show_deletion_blockers <user-uuid>
"""

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.core.models import User
from apps.core.models.users import (
    BLOCKING_ON_DELETE,
    LANDPKS_APP_LABELS,
    SYSTEM_APP_LABELS,
)

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
    """Return blocker dicts for rows that would block this user's
    soft-deletion. Empty list = safe to soft-delete.

    Each blocker is `{model, qualifier, field, count, ids}` where
    `qualifier` is Optional[str] (None unless the model needs a sub-
    classification like membership type) and `ids` is up to
    BLOCKER_ID_CAP pk strings; `count` is the true total so renderers
    can compute "+N more" when ids are truncated.

    Classification: a reverse FK to User blocks if its on_delete is
    PROTECT/RESTRICT and the referencing model isn't in
    LANDPKS_APP_LABELS (handled by an explicit cascade) or
    SYSTEM_APP_LABELS (Django internals). The single policy override
    is non-project APPROVED collaboration.Memberships — they're
    CASCADE at the DB level but flagged as blockers because
    Group/Landscape membership is web data we don't auto-delete.

    Only active rows count — soft-deleted referencers are handled by
    the resilient harddelete cron in subsequent runs.

    Walks one layer deep (direct reverse FKs from User). Deeper
    coverage (transitive cascade closure) is enforced by the
    structural test in tests/core/models/test_user_deletion_gate.py.
    """
    blockers = []
    for rel in User._meta.related_objects:
        if rel.many_to_many:
            continue  # through-rows auto-cleaned
        related_model = rel.related_model
        app = related_model._meta.app_label
        if app in LANDPKS_APP_LABELS or app in SYSTEM_APP_LABELS:
            continue

        if related_model._meta.label == "collaboration.Membership":
            from apps.collaboration.models import Membership

            # Policy override: non-project APPROVED memberships block
            # even though Membership.user is CASCADE (the on_delete-
            # floor rule would otherwise let them through). Project
            # vs. non-project is distinguished by
            # `membership_list__project__isnull`.
            qs = user.collaboration_memberships.filter(
                membership_list__project__isnull=True,
                membership_status=Membership.APPROVED,
            )
            count = qs.count()
            if count > 0:
                blockers.append(
                    {
                        "model": "collaboration.Membership",
                        "qualifier": "non-project, approved",
                        "field": "user",
                        "count": count,
                        "ids": [str(pk) for pk in qs.values_list("pk", flat=True)[:BLOCKER_ID_CAP]],
                    }
                )
            continue

        on_delete_name = rel.on_delete.__name__.upper()
        if on_delete_name not in BLOCKING_ON_DELETE:
            continue

        # Only active rows block. A row that's already soft-deleted is
        # handled by the harddelete cron (which sorts by deleted_at and
        # is resilient to per-row integrity failures), so it doesn't
        # need to gate the user.
        qs = related_model.objects.filter(**{rel.field.name: user})
        count = qs.count()
        if count > 0:
            blockers.append(
                {
                    "model": related_model._meta.label,
                    "qualifier": None,
                    "field": rel.field.name,
                    "count": count,
                    "ids": [str(pk) for pk in qs.values_list("pk", flat=True)[:BLOCKER_ID_CAP]],
                }
            )
    return blockers


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
