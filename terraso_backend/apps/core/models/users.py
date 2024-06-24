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

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from safedelete.models import SOFT_DELETE_CASCADE, SafeDeleteManager, SafeDeleteModel

from apps.core import group_collaboration_roles, landscape_collaboration_roles

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

    def soft_delete_policy_action(self, **kwargs):
        """Relink files to deleted user. The default policy is to set the `created_by` field to
        null if the user is deleted. However, for a soft deletion we want to keep this link. That
        way if the user is restored, the created_by is still pointing to the same place."""
        linked_dataentries = self.dataentry_set.all()
        delete_response = super().soft_delete_policy_action()
        for entry in linked_dataentries:
            entry.created_by = self
            entry.save()
        return delete_response

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
