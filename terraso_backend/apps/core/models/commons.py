import uuid

from django.db import models
from django.utils.text import slugify
from rules.contrib.models import RulesModelBase, RulesModelMixin
from safedelete.models import SOFT_DELETE_CASCADE, SafeDeleteModel


class BaseModel(RulesModelMixin, SafeDeleteModel, metaclass=RulesModelBase):
    _safedelete_policy = SOFT_DELETE_CASCADE

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        get_latest_by = "-created_at"
        ordering = ["created_at"]


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
                name="unique_active_slug",
            ),
        )
