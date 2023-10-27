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

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel, SlugModel, User
from apps.core.models.commons import validate_name
from apps.shared_data import permission_rules as perm_rules

from .data_entries import DataEntry


class VisualizationConfig(SlugModel):
    MAPBOX_TILESET_PENDING = "pending"
    MAPBOX_TILESET_READY = "ready"

    MAPBOX_TILESET_STATUSES = (
        (MAPBOX_TILESET_PENDING, _("Pending")),
        (MAPBOX_TILESET_READY, _("Ready")),
    )

    title = models.CharField(max_length=128, validators=[validate_name])
    configuration = models.JSONField(blank=True, null=True)
    created_by = models.ForeignKey(
        User,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="created_visualization_configs",
    )
    mapbox_tileset_id = models.CharField(max_length=128, blank=True, null=True)
    mapbox_tileset_status = models.CharField(
        max_length=128, choices=MAPBOX_TILESET_STATUSES, default=MAPBOX_TILESET_PENDING
    )
    data_entry = models.ForeignKey(
        DataEntry, on_delete=models.CASCADE, related_name="visualizations"
    )
    owner = GenericForeignKey("owner_content_type", "owner_object_id")
    owner_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="owner_content_type",
        null=True,
        blank=True,
    )
    owner_object_id = models.UUIDField(null=True, blank=True)

    field_to_slug = "title"

    class Meta(BaseModel.Meta):
        constraints = (
            models.UniqueConstraint(
                fields=("owner_object_id", "slug"),
                condition=models.Q(deleted_at__isnull=True),
                name="shared_data_visualizationconfig_unique_active_slug_by_owner",
            ),
        )
        verbose_name_plural = "Visualization Configs"
        rules_permissions = {
            "add": perm_rules.allowed_to_add_visualization_config,
            "change": perm_rules.allowed_to_change_visualization_config,
            "delete": perm_rules.allowed_to_delete_visualization_config,
            "view": perm_rules.allowed_to_view_visualization_config,
        }
