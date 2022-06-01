import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from safedelete.models import SOFT_DELETE_CASCADE, SafeDeleteManager, SafeDeleteModel


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

    def is_landscape_manager(self, landscape_id):
        return (
            self.memberships.managers_only()
            .filter(
                group__associated_landscapes__is_default_landscape_group=True,
                group__associated_landscapes__landscape__pk=landscape_id,
            )
            .exists()
        )

    def is_group_manager(self, group_id):
        return self.memberships.managers_only().filter(group__pk=group_id).exists()

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
