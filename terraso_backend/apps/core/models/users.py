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

# Apps whose models cascade with the user (the "landpks subtree"). These
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
        return (
            self.collaboration_memberships.by_role(landscape_collaboration_roles.ROLE_MANAGER)
            .filter(
                membership_list__landscape__pk=landscape_id,
            )
            .exists()
        )

    def is_group_manager(self, group_id):
        return (
            self.collaboration_memberships.by_role(group_collaboration_roles.ROLE_MANAGER)
            .filter(
                membership_list__group__pk=group_id,
            )
            .exists()
        )

    def deletion_blockers(self):
        """Return a list of {model, field, count} dicts for any rows that
        would block soft-deletion of this user. Empty list means the user
        is safe to soft-delete.

        Classification rule (see design doc backend/docs/user_soft_delete_plan.md):

          1. Many-to-many reverse relations are skipped — through-rows auto-clean.
          2. Apps in LANDPKS_APP_LABELS are torn down explicitly in soft_delete_policy_action; SYSTEM_APP_LABELS are Django internals. Both skip.
          3. collaboration.Membership is a policy special case: non-project approved memberships count as blockers. (Group/Landscape membership is web data we are not yet deleting automatically. Pending memberships are not blockers.)
          4. Otherwise the on_delete behavior decides: PROTECT / RESTRICT / DO_NOTHING auto-block; CASCADE / SET_NULL / SET_DEFAULT / SET auto-allow (referentially safe at hard-delete).
          5. Rows that were already soft-deleted should still block (force_visibility=True for SafeDeleteModels) until the harddelete cron purges it, to avoid a crash on harddelete. This means if a user soft-deletes their only story map on day 0, they can't delete their LandPKS account until the hard-delete cron job run on day 30. Because if they also soft-delete their account on day 0, on day 30 the cron could attempt to hard-delete the User before hard-deleting the StoryMap -- whose foreign key to user is DO_NOTHING, which would cause a DB-level integrity error.

        SCOPE — one layer only. This walks ONLY direct reverse FKs from
        User (`User._meta.related_objects`). It does NOT recurse through
        related models. A blocking FK pointing at a *descendant* of User
        in the cascade (e.g. a hypothetical SpecialData.site = ForeignKey(
        Site, PROTECT) in some future app) is not surfaced here, even
        though it would crash the harddelete cron when Site is purged.

        Deeper coverage comes from the structural test
        `test_structural_user_deletion_closure_is_hard_delete_safe` in
        tests/core/models/test_user_deletion_gate.py, which walks the
        transitive closure of the cascade and fails CI if any closure
        model is referenced via a blocking FK. Together, this one-layer
        check and the closure test cover the full cascade tree.
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

                # Policy override: non-project APPROVED memberships block.
                # ProjectMembershipList is a proxy of MembershipList; project
                # lists are distinguished by `membership_list__project__isnull`
                # (the established pattern; see UserFilter in
                # apps/graphql/schema/users.py).
                count = self.collaboration_memberships.filter(
                    membership_list__project__isnull=True,
                    membership_status=Membership.APPROVED,
                ).count()
                if count > 0:
                    blockers.append(
                        {
                            "model": "collaboration.Membership (non-project, approved)",
                            "field": "user",
                            "count": count,
                        }
                    )
                continue

            on_delete_name = rel.on_delete.__name__.upper()
            if on_delete_name not in BLOCKING_ON_DELETE:
                continue

            if issubclass(related_model, SafeDeleteModel):
                base_qs = related_model.objects.all(force_visibility=True)
            else:
                base_qs = related_model.objects.all()
            count = base_qs.filter(**{rel.field.name: self}).count()
            if count > 0:
                blockers.append(
                    {
                        "model": related_model._meta.label,
                        "field": rel.field.name,
                        "count": count,
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
            raise ValidationError(
                f"Cannot delete user {self.email!r}: has undeletable data "
                f"({len(blockers)} blocking model(s))."
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
        from apps.project_management.models import Project

        solo_project_ids = list(self._solo_manager_projects().values_list("pk", flat=True))
        result = super().delete(*args, **kwargs)
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

    def undelete(self, *args, **kwargs):
        """Restore a soft-deleted user, refusing if their email is already
        in use by another active user.

        Email uniqueness is conditional on `deleted_at__isnull=True` (see
        Meta.constraints), so a soft-deleted user's email can be re-
        registered by someone else during the grace window. Letting
        undelete succeed in that case would raise a generic IntegrityError
        from the DB. Detect the conflict explicitly and surface a clear
        message instead.

        NOTE: undelete restores the User row and the soft-deleted related
        rows (Memberships, sole-manager Projects + their MembershipLists,
        owned Sites + soil data). It does NOT recover `SiteNote.author`
        rows nulled at hard-delete (those FKs are gone forever), nor any
        rows that were refused at the soft-delete gate. Restoration is
        partial by design.
        """
        conflict = type(self).objects.filter(email=self.email).exclude(pk=self.pk).first()
        if conflict is not None:
            raise ValidationError(
                f"Cannot undelete user {self.email!r}: another active user "
                f"with that email already exists (id={conflict.id}). "
                "Resolve the conflict before undeleting."
            )
        return super().undelete(*args, **kwargs)

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


# Deleted-user stub: returned by resolvers (SiteNoteNode.author,
# SiteNode.owner) when the underlying FK is null after a SET_NULL
# cascade from UserDeleteMutation.  See deleted_user_stub_plan.md
# in terraso-backend-research for the rationale.
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

    Used by GraphQL resolvers to keep the `author: User!` /
    `owner: User!` schema contract intact when the FK is null on a
    soft-deleted authoring user.

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
