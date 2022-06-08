import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from rules.contrib.models import RulesModelBase, RulesModelMixin
from safedelete.models import SOFT_DELETE_CASCADE, SafeDeleteModel


def validate_name(value):
    if value.lower() in settings.DISALLOWED_NAMES_LIST:
        raise ValidationError(
            _("%(value)s is not allowed as a name"), params={"value": value}, code="invalid"
        )


class BaseModel(RulesModelMixin, SafeDeleteModel, metaclass=RulesModelBase):
    _safedelete_policy = SOFT_DELETE_CASCADE

    fields_to_trim = []

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        get_latest_by = "-created_at"
        ordering = ["created_at"]

    def save(self, *args, **kwargs):
        for field in self.fields_to_trim:
            setattr(self, field, getattr(self, field).strip())
        return super().save(*args, **kwargs)


class SlugModel(BaseModel):
    slug = models.SlugField(max_length=250, blank=True, editable=False)

    def save(self, *args, **kwargs):
        value_to_slugify = getattr(self, self.field_to_slug)
        self.slug = slugify(value_to_slugify)
        return super().save(*args, **kwargs)

    class Meta(BaseModel.Meta):
        abstract = True
        constraints = (
            models.UniqueConstraint(
                fields=("slug",),
                condition=models.Q(deleted_at__isnull=True),
                name="%(app_label)s_%(class)s_unique_active_slug",
            ),
        )
