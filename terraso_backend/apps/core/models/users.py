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
from django.db.models.deletion import ProtectedError, RestrictedError
from django.utils.translation import gettext_lazy as _
from safedelete.models import HARD_DELETE, SOFT_DELETE_CASCADE, SafeDeleteManager, SafeDeleteModel

from apps.core import group_collaboration_roles, landscape_collaboration_roles

logger = structlog.get_logger(__name__)

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
    """Raised by `User.delete()` (soft path) when the user has data that
    would block deletion — either a policy blocker (non-project APPROVED
    Membership) or a PROTECT/RESTRICT reverse FK that safedelete's
    collector refused. Subclasses `ValidationError` for backwards
    compatibility.

    Details of what's blocking aren't carried on the exception; callers
    who need them run the `show_deletion_blockers` management command.
    """


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

    def delete(self, *args, **kwargs):
        """Gate soft-delete, then tear down solo-manager projects. Two
        block sources:

          1. Non-project APPROVED Memberships. Membership.user is
             CASCADE at the DB layer so safedelete's collector won't
             raise for them, but Group/Landscape membership is web data
             we don't auto-delete. Checked upfront.
          2. PROTECT/RESTRICT reverse FKs (Group/Landscape/TaxonomyTerm/
             VisualizationConfig/StoryMap/DataEntry `created_by`).
             safedelete's collector raises `ProtectedError`/
             `RestrictedError` from `super().delete()` before touching
             the DB — caught here and re-raised as our own type.

        Hard-delete is intentionally not gated — the harddelete cron is
        generic and must stay robust; all cleanup happens at the
        soft-delete boundary.

        Why the project cascade lives here rather than in
        soft_delete_policy_action: safedelete's SOFT_DELETE_CASCADE soft-deletes
        the user's Memberships *before* invoking soft_delete_policy_action, so
        a "solo-manager projects" query that filters on `deleted_at IS NULL`
        Memberships would find none of them by the time it runs. We capture the
        project IDs up here, then iterate them after super() returns.

        Callers who need specifics of what's blocking run
        `python manage.py show_deletion_blockers <email>`

        See tests/core/models/test_user_deletion_gate.py.
        """
        if kwargs.get("force_policy") == HARD_DELETE:
            return super().delete(*args, **kwargs)

        if self._special_blockers_exist():
            raise UserDeletionBlockedError(self._blocked_message())

        try:
            result = self._soft_delete_with_cascade(*args, **kwargs)
        except (ProtectedError, RestrictedError):
            logger.warning(
                "user.delete_blocked",
                target_user_id=str(self.id),
                reason="protected_fk",
            )
            raise UserDeletionBlockedError(self._blocked_message())

        logger.info("user.soft_deleted", target_user_id=str(self.id))
        return result

    def _special_blockers_exist(self):
        "Any additional blockers to deleting a User, outside of the PROTECT/RESTRICT reverse foreign keys."
        "NOTE! If logic is added or changed here, please update the show_deletion_blockers.py script to report blockers accordingly"

        if self._non_project_approved_memberships().exists():
            logger.warning(
                "user.delete_blocked",
                target_user_id=str(self.id),
                reason="non_project_approved_membership",
            )
            return True

        return False

    def _non_project_approved_memberships(self):
        """Policy blocker query: non-project APPROVED Memberships that
        would otherwise CASCADE with the user."""
        from apps.collaboration.models import Membership

        return self.collaboration_memberships.filter(
            membership_list__project__isnull=True,
            membership_status=Membership.APPROVED,
        )

    def _blocked_message(self):
        return (
            f"Cannot delete user {self.email!r}: undeletable data exists. "
            f"For details, run 'python manage.py show_deletion_blockers {self.email}' or 'make show-deletion-blockers user={self.email}'."
        )

    @transaction.atomic
    def _soft_delete_with_cascade(self, *args, **kwargs):
        """Soft-delete this user. Includes cascade deletion plus special logic that safedelete's cascade can't reach."""
        solo_project_ids = list(self._solo_manager_projects().values_list("pk", flat=True))
        self._stash_site_note_authorship()
        result = super().delete(*args, **kwargs)
        self._soft_delete_solo_manager_projects(solo_project_ids)
        return result

    def _stash_site_note_authorship(self):
        """Copy `author` → `saved_author` on SiteNotes we authored, before
        the SET_NULL cascade blanks `author`. `undelete` reads `saved_author`
        to restore the link — only works if the user row has not been hard=deleted."""
        from apps.project_management.models import SiteNote

        SiteNote.all_objects.filter(author=self).update(saved_author=self.pk)

    def _soft_delete_solo_manager_projects(self, project_ids):
        """Soft-delete the captured projects.
        Note: don't pass is_cascade=True, because safedelete sets it during its own recursion and passing it again trips a duplicate-keyword TypeError. Consequence: the Project row shows `deleted_by_cascade=False` (descendants still read True)."""
        from apps.project_management.models import Project

        for project in Project.objects.filter(pk__in=project_ids):
            project.delete()

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
        """Restore this user plus what was cleaned up alongside them (like solo-manager projects, SiteNote authorship).
        Refuses if another active user has taken the email during the grace window — the unique_active_email constraint would otherwise raise IntegrityError.
        Restoration only works for soft-deleted objects; anything hard-deleted is gone forever."""
        conflict = type(self).objects.filter(email=self.email).exclude(pk=self.pk).first()
        if conflict is not None:
            raise ValidationError(
                f"Cannot undelete user {self.email!r}: another active user "
                f"with that email already exists (id={conflict.id}). "
                "Resolve the conflict before undeleting."
            )
        result = super().undelete(*args, **kwargs)
        self._undelete_solo_manager_projects()
        self._restore_site_note_authorship()
        return result

    def _undelete_solo_manager_projects(self):
        """Mirror of _soft_delete_solo_manager_projects. After super()
        restores the user's Memberships, any MANAGER membership whose
        MembershipList belongs to a still-soft-deleted Project is one we
        explicitly deleted at soft-delete time. Undelete it — Project.undelete
        restores the MembershipList + other Memberships; safedelete's cascade
        handles Sites + soil data. No solo-manager re-check needed: a
        soft-deleted Project can't have gained new managers meanwhile."""
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

    def _restore_site_note_authorship(self):
        """Mirror of _stash_site_note_authorship."""
        from apps.project_management.models import SiteNote

        SiteNote.all_objects.filter(saved_author=self.pk, author__isnull=True).update(
            author=self, saved_author=None
        )

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


def request_account_deletion(user):
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
    if not create_account_deletion_ticket(user):
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
