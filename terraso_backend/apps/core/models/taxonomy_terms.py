from django.db import models

from .commons import SlugModel, validate_name
from .users import User


class TaxonomyTerm(SlugModel):

    name = models.CharField(max_length=128, unique=True, validators=[validate_name])
    type = models.CharField(max_length=128, unique=True, validators=[validate_name])

    created_by = models.ForeignKey(
        User,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="created_taxonomy_terms",
    )

    field_to_slug = "name"

    def __str__(self):
        return "{}.{}".format(self.type, self.name)

    class Meta(SlugModel.Meta):
        constraints = (
            models.UniqueConstraint(
                fields=(
                    "type",
                    "slug",
                ),
                condition=models.Q(deleted_at__isnull=True),
                name="%(app_label)s_%(class)s_unique_active_slug",
            ),
        )
