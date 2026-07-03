# Copyright © 2021-2023 Technology Matters
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

import uuid

import structlog
from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from safedelete.models import HARD_DELETE, SOFT_DELETE_CASCADE, SafeDeleteManager, SafeDeleteModel

from apps.core import group_collaboration_roles, landscape_collaboration_roles

logger = structlog.get_logger(__name__)

# Used for User deletion: Apps whose models cascade with the user
# (the "landpks subtree"). These
# are torn down explicitly in User._soft_delete_with_cascade and
# Project.soft_delete_policy_action — rather than blocked by the gate —
# because the schema is set up so the cascade can clean them up safely.
#
# Two structural tests in tests/core/models/test_user_deletion_gate.py
# enforce the invariants this allowlist relies on:
#   - Test A: every reverse FK from any app to User is classified into
#     one legal bucket (so a new PROTECT FK to User can't go unnoticed).
#   - "closure is hard-delete safe": every model in the user-deletion
#     cascade closure (which includes everything in LANDPKS_APP_LABELS)
#     is asserted to have no incoming blocking FKs — so the harddelete
#     cron can purge the closure cleanly when the grace window expires.
#
# To add a new domain app whose data should cascade with the user
# (rather than block at the gate), add its app_label here and confirm
# the closure structural test still passes.
LANDPKS_APP_LABELS = {"project_management", "soil_id"}
# Django internals — reverse FKs to User in these apps are auto-allowed
# (Django manages them itself).
SYSTEM_APP_LABELS = {"admin", "auth", "contenttypes", "sessions"}
# on_delete behaviors that either raise or orphan at hard-delete time,
# so a row pointing at the User through one of these FKs blocks deletion.
BLOCKING_ON_DELETE = {"PROTECT", "RESTRICT", "DO_NOTHING"}

# Cap pk strings attached to each blocker. `count` is always the true
# total; renderers show "+N more" from `count - len(ids)`.
BLOCKER_ID_CAP = 50

USER_PREFS_KEY_GROUP_NOTIFICATIONS = "group_notifications"
USER_PREFS_KEY_STORY_MAP_NOTIFICATIONS = "story_map_notifications"
USER_PREFS_KEY_LANGUAGE = "language"
USER_PREFS_KEY_ACCOUNT_DELETION = "account_deletion_request"
USER_PREFS_KEYS = [
    USER_PREFS_KEY_GROUP_NOTIFICATIONS,
    USER_PREFS_KEY_STORY_MAP_NOTIFICATIONS,
    USER_PREFS_KEY_LANGUAGE,
    USER_PREFS_KEY_ACCOUNT_DELETION,
]


class UserManager(SafeDeleteManager, BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """Create and save a User with the given email and password."""
        if not email:
            raise ValueError("The given email must be set")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular User with the given email and password."""
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        """Create and save a SuperUser with the given email and password."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class UserDeletionBlockedError(ValidationError):
    """Raised by `User.delete()` (soft path) when `deletion_blockers()` is
    non-empty. Subclasses `ValidationError` for backwards compatibility.
    Carries `.blockers` so callers reuse it without re-querying."""

    def __init__(self, message, blockers):
        super().__init__(message)
        self.blockers = blockers


def format_blocker(b):
    """Render one blocker dict as "<label>: <detail>" for admin banner
    and HubSpot ticket body. Truncated `ids` show with "(+N more)"."""
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


class User(SafeDeleteModel, AbstractUser):
    """This model represents a User on Terraso platform."""

    fields_to_trim = ["first_name", "last_name"]

    _safedelete_policy = SOFT_DELETE_CASCADE

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    username = None
    email = models.EmailField()
    profile_image = models.URLField(blank=True, default="")
    # Apple's stable per-(Apple ID, developer team) user identifier ("sub" claim
    # of the id_token). Recorded on first successful Apple sign-in so we can
    # look users up by sub on subsequent sign-ins where Apple omits the email
    # claim from the id_token (which can happen on degraded auth state, e.g.
    # after revoke + re-auth cycles). Null for users who have never signed in
    # via Apple, or for legacy Apple users not yet backfilled.
    apple_sub = models.CharField(max_length=255, blank=True, null=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        get_latest_by = "created_at"
        ordering = ["-created_at"]
        constraints = (
            models.UniqueConstraint(
                fields=("email",),
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_email",
            ),
            models.UniqueConstraint(
                fields=("apple_sub",),
                condition=models.Q(apple_sub__isnull=False) & models.Q(deleted_at__isnull=True),
                name="unique_active_apple_sub",
            ),
        )

    def save(self, *args, **kwargs):
        for field in self.fields_to_trim:
            setattr(self, field, getattr(self, field).strip())
        return super().save(*args, **kwargs)

    def is_landscape_manager(self, landscape_id):
        if landscape_id is None:
            return False

        return (
            self.collaboration_memberships.by_role(landscape_collaboration_roles.ROLE_MANAGER)
            .filter(
                membership_list__landscape__pk=landscape_id,
            )
            .exists()
        )

    def is_group_manager(self, group_id):
        if group_id is None:
            return False

        return (
            self.collaboration_memberships.by_role(group_collaboration_roles.ROLE_MANAGER)
            .filter(
                membership_list__group__pk=group_id,
            )
            .exists()
        )

    def deletion_blockers(self):
        """Return blocker dicts for rows that would block this user's
        soft-deletion. Empty list = safe to soft-delete.

        Each blocker is `{model, qualifier, field, count, ids}` where
        `qualifier` is Optional[str] (None unless the model needs a sub-
        classification like membership type) and `ids` is up to
        BLOCKER_ID_CAP pk strings; `count` is the true total so renderers
        can compute "+N more" when ids are truncated.

        Classification: a reverse FK to User blocks if its on_delete is
        PROTECT/RESTRICT/DO_NOTHING and the referencing model isn't in
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
                qs = self.collaboration_memberships.filter(
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
                            "ids": [
                                str(pk) for pk in qs.values_list("pk", flat=True)[:BLOCKER_ID_CAP]
                            ],
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
            qs = related_model.objects.filter(**{rel.field.name: self})
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

    def delete(self, *args, **kwargs):
        """Gate soft-delete on deletion_blockers(), then tear down sole-manager
        projects. Hard-delete is intentionally not gated — the harddelete cron
        is generic and must stay robust; all cleanup happens at the soft-delete
        boundary.

        Why the project cascade lives here rather than in
        soft_delete_policy_action: safedelete's SOFT_DELETE_CASCADE soft-deletes
        the user's Memberships *before* invoking soft_delete_policy_action, so
        a "sole-manager projects" query that filters on `deleted_at IS NULL`
        Memberships would find none of them by the time it runs. We capture the
        project IDs up here, then iterate them after super() returns."""
        if kwargs.get("force_policy") == HARD_DELETE:
            return super().delete(*args, **kwargs)

        blockers = self.deletion_blockers()
        if blockers:
            logger.warning(
                "user.delete_blocked",
                target_user_id=str(self.id),
                blockers=blockers,
            )
            raise UserDeletionBlockedError(
                f"Cannot delete user {self.email!r}: has undeletable data "
                f"({len(blockers)} blocking model(s)).",
                blockers=blockers,
            )
        logger.info("user.soft_deleted", target_user_id=str(self.id))

        return self._soft_delete_with_cascade(*args, **kwargs)

    @transaction.atomic
    def _soft_delete_with_cascade(self, *args, **kwargs):
        """Soft-delete this user and the sole-manager projects they leave behind.

        Unaffiliated owned sites: handled by Site.owner=CASCADE plus safedelete's
        SOFT_DELETE_CASCADE; their soil/notes/history subtrees cascade
        automatically.

        Sole-manager projects: explicit — there's no FK that says "this project
        belongs to this user". Project.soft_delete_policy_action handles the
        MembershipList cleanup for each."""
        from apps.project_management.models import Project, SiteNote

        solo_project_ids = list(self._solo_manager_projects().values_list("pk", flat=True))
        # Preserve authorship before the SET_NULL cascade blanks SiteNote.author.
        # These notes (on other users' sites) survive this soft-delete with a null
        # author; stashing the id lets undelete() put the author back.
        SiteNote.all_objects.filter(author=self).update(saved_author=self.pk)
        result = super().delete(*args, **kwargs)
        # Note: not passing is_cascade=True. safedelete hardcodes
        # is_cascade=True when recursing internally AND forwards **kwargs,
        # so passing it from the outside trips a duplicate-keyword
        # TypeError. Restoration on undelete is driven by the explicit
        # walk in _undelete_solo_manager_projects, not the cascade flag.
        #
        # Minor consequence: the soft-deleted Project row will have
        # `deleted_by_cascade=False` even though it was semantically
        # cascade-deleted from this user. Cascade descendants under the
        # Project (Sites, soil data, etc.) still correctly read True —
        # those go through safedelete's internal recursion. Only the
        # explicit Project "root" we delete here is mislabelled.
        for project in Project.objects.filter(pk__in=solo_project_ids):
            project.delete()
        return result

    def _solo_manager_projects(self):
        """Projects where this user is the sole APPROVED, non-soft-deleted
        manager. Annotated single query instead of a query per project."""
        from django.db.models import Count, IntegerField, OuterRef, Subquery

        from apps.collaboration.models import Membership
        from apps.project_management.collaboration_roles import ProjectRole
        from apps.project_management.models import Project

        # Count approved managers per project (SafeDeleteManager hides
        # soft-deleted memberships, matching the soundness requirement).
        manager_count_subquery = (
            Membership.objects.filter(
                membership_list__project=OuterRef("pk"),
                user_role=ProjectRole.MANAGER.value,
                membership_status=Membership.APPROVED,
            )
            .values("membership_list__project")
            .annotate(c=Count("id"))
            .values("c")
        )
        return (
            Project.objects.filter(
                membership_list__memberships__user=self,
                membership_list__memberships__user_role=ProjectRole.MANAGER.value,
                membership_list__memberships__membership_status=Membership.APPROVED,
                membership_list__memberships__deleted_at__isnull=True,
            )
            .annotate(manager_count=Subquery(manager_count_subquery, output_field=IntegerField()))
            .filter(manager_count=1)
            .distinct()
        )

    @transaction.atomic
    def undelete(self, *args, **kwargs):
        """Restore a soft-deleted user, refusing if their email is already
        in use by another active user.

        Email uniqueness is conditional on `deleted_at__isnull=True` (see
        Meta.constraints), so a soft-deleted user's email can be re-
        registered by someone else during the grace window. Letting
        undelete succeed in that case would raise a generic IntegrityError
        from the DB. Detect the conflict explicitly and surface a clear
        message instead.

        Restores the User row and the soft-deleted related rows (Memberships,
        owned Sites + soil data + notes — all via safedelete's
        cascade-walker), plus sole-manager Projects + their MembershipLists
        + cascade-children (via an explicit walk in
        _undelete_solo_manager_projects, because Project has no reverse FK
        to User and isn't reachable from User by safedelete's walker).

        Restores `SiteNote.author` from the `saved_author` shadow stashed at
        soft-delete time (see _soft_delete_with_cascade). This only works while
        the user row still exists: once hard-deleted the author is gone forever
        (as is anything refused at the gate). Restoration is partial by design.
        """
        from apps.project_management.models import SiteNote

        conflict = type(self).objects.filter(email=self.email).exclude(pk=self.pk).first()
        if conflict is not None:
            raise ValidationError(
                f"Cannot undelete user {self.email!r}: another active user "
                f"with that email already exists (id={conflict.id}). "
                "Resolve the conflict before undeleting."
            )
        result = super().undelete(*args, **kwargs)
        self._undelete_solo_manager_projects()
        # Restore authorship blanked by the SET_NULL cascade, and clear the
        # shadow. Scoped to notes we nulled for this user (author still null).
        SiteNote.all_objects.filter(saved_author=self.pk, author__isnull=True).update(
            author=self, saved_author=None
        )
        return result

    def _undelete_solo_manager_projects(self):
        """Restore Projects this user was the sole manager of at deletion time.

        After super().undelete(), the user's Memberships are restored. Walk
        their MANAGER memberships: any whose MembershipList belongs to a
        still-soft-deleted Project is one we explicitly deleted in
        _soft_delete_with_cascade. Undelete it — Project.undelete in turn
        restores the MembershipList and its other Memberships, and
        safedelete's standard cascade-walker handles the Sites / soil data
        subtree.

        We don't need to re-check sole-manager status here: a Project that's
        soft-deleted can't have gained new managers in the meantime."""
        from apps.collaboration.models import Membership
        from apps.project_management.collaboration_roles import ProjectRole
        from apps.project_management.models import Project

        manager_memberships = self.collaboration_memberships.filter(
            user_role=ProjectRole.MANAGER.value,
            membership_status=Membership.APPROVED,
        )
        for m in manager_memberships:
            project = Project.all_objects.filter(membership_list_id=m.membership_list_id).first()
            if project is not None and project.deleted_at is not None:
                project.undelete()

    def full_name(self):
        return _(
            "%(first_name)s %(last_name)s"
            % {"first_name": self.first_name, "last_name": self.last_name}
        )

    def name_and_email(self):
        return f"'{self.full_name()}' <{self.email}>"

    def group_notifications_enabled(self):
        return self._notifications_enabled(USER_PREFS_KEY_GROUP_NOTIFICATIONS)

    def story_map_notifications_enabled(self):
        return self._notifications_enabled(USER_PREFS_KEY_STORY_MAP_NOTIFICATIONS)

    def _notifications_enabled(self, key):
        preferences = self.preferences.filter(key=key)
        if len(preferences) != 1 or not hasattr(preferences[0], "value"):
            return False

        return preferences[0].value.lower() == "true"

    def language(self):
        preferences = self.preferences.filter(key="language")
        if len(preferences) != 1 or not hasattr(preferences[0], "value"):
            return settings.DEFAULT_LANGUAGE_CODE

        language_code = preferences[0].value
        if language_code[0:2] in [lang[0] for lang in settings.LANGUAGES]:
            return language_code.lower()
        else:
            return settings.DEFAULT_LANGUAGE_CODE

    def __str__(self):
        return self.email


class UserPreference(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    key = models.CharField(max_length=128)
    value = models.CharField(max_length=512, blank=True, default="")

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="preferences")

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("key", "user"),
                name="unique_user_preference",
            ),
        )


class TicketCreationError(Exception):
    """Raised by `request_account_deletion` when the HubSpot ticket call
    reports failure. Surfacing this lets the caller retry instead of
    silently locking the user out via the idempotence check."""


def request_account_deletion(user, blockers=None):
    """Set the pending-deletion pref and file the HubSpot ticket exactly
    once. Idempotent if the pref is already "true". Caller gates permission.

    Order: ticket BEFORE pref. If HubSpot fails, pref stays "false" so the
    caller can retry. Reverse order would silently lock the user out via
    the idempotence short-circuit (pref stuck at "true" with no ticket).
    """
    from apps.core.hubspot import create_account_deletion_ticket

    pref, _ = UserPreference.objects.get_or_create(user=user, key=USER_PREFS_KEY_ACCOUNT_DELETION)
    if pref.value.lower() == "true":
        return
    if not create_account_deletion_ticket(user, blockers=blockers):
        raise TicketCreationError(
            f"Failed to file HubSpot account-deletion ticket for {user.email!r}"
        )
    pref.value = "true"
    pref.save()


# Deleted-user stub: returned by SiteNoteNode.author when the FK is null
#
# Old clients that don't know about the sentinel render `firstName +
# lastName` verbatim ("Deleted User", English).  New clients import
# the sentinel id from terraso-client-shared and substitute a
# locale-aware label via i18n.
DELETED_USER_ID = "00000000-0000-0000-0000-000000000000"
DELETED_USER_FIRST_NAME = "Deleted"
DELETED_USER_LAST_NAME = "User"


def deleted_user_stub():
    """Return an unsaved User instance representing a deleted account.

    Used by the SiteNoteNode.author resolver to keep the `author: User!`
    schema contract intact when the FK is null on a soft-deleted
    authoring user (SiteNote.author is SET_NULL on cascade).

    `is_active=False` is set explicitly so the stub serializes the
    semantically-correct value if `is_active` is ever exposed on
    UserNode, and as defense-in-depth against the stub accidentally
    reaching Django's `authenticate()` (which rejects inactive users).
    """
    return User(
        id=DELETED_USER_ID,
        first_name=DELETED_USER_FIRST_NAME,
        last_name=DELETED_USER_LAST_NAME,
        email="",
        profile_image="",
        is_active=False,
    )
