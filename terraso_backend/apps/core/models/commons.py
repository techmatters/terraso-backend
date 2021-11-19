import uuid

from django.db import models
from django.utils.text import slugify


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        get_latest_by = "-created_at"
        ordering = ["created_at"]


class SlugModel(BaseModel):
    slug = models.SlugField(max_length=250, unique=True, blank=True, editable=False)

    def save(self, *args, **kwargs):
        if not self.slug:
            value_to_slugify = getattr(self, self.field_to_slug)
            self.slug = slugify(value_to_slugify)
        return super().save(*args, **kwargs)

    class Meta(BaseModel.Meta):
        abstract = True
