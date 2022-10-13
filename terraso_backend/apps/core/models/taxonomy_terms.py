from django.db import models
from django.utils.translation import gettext_lazy as _

from .commons import SlugModel, validate_name
from .users import User


class TaxonomyTerm(SlugModel):
    TYPE_ECOSYSTEM_TYPE = "ecosystem-type"
    TYPE_LANGUAGE = "language"
    TYPE_LIVELIHOOD = "livelihood"
    TYPE_COMMODITY = "commodity"
    TYPE_ORGANIZATION = "organization"

    TYPES = (
        (TYPE_ECOSYSTEM_TYPE, _("Ecosystem Type")),
        (TYPE_LANGUAGE, _("Language")),
        (TYPE_LIVELIHOOD, _("Livelihood")),
        (TYPE_COMMODITY, _("Commodity")),
        (TYPE_ORGANIZATION, _("Organization")),
    )

    name = models.CharField(max_length=128, unique=True, validators=[validate_name])
    type = models.CharField(max_length=128, unique=True, choices=TYPES)

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
