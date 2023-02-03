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
    TYPE_AGRICULTURAL_PRODUCTION_METHOD = "agricultural-production-method"

    TYPES = (
        (TYPE_ECOSYSTEM_TYPE, _("Ecosystem Type")),
        (TYPE_LANGUAGE, _("Language")),
        (TYPE_LIVELIHOOD, _("Livelihood")),
        (TYPE_COMMODITY, _("Commodity")),
        (TYPE_ORGANIZATION, _("Organization")),
        (TYPE_AGRICULTURAL_PRODUCTION_METHOD, _("Agricultural Production Method")),
    )

    value_original = models.CharField(max_length=128, validators=[validate_name])
    value_es = models.CharField(max_length=128, blank=True, default="")
    value_en = models.CharField(max_length=128, blank=True, default="")
    type = models.CharField(max_length=128, choices=TYPES)

    created_by = models.ForeignKey(
        User,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="created_taxonomy_terms",
    )

    field_to_slug = "value_original"

    def __str__(self):
        return "{}.{}".format(self.type, self.slug)

    class Meta(SlugModel.Meta):
        _ignore_unique_fields = ["slug"]
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
