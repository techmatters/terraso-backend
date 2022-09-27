from django.db import models

from apps.core.models import BaseModel, Group, SlugModel, User
from apps.core.models.commons import validate_name
from apps.shared_data import permission_rules as perm_rules

from .data_entries import DataEntry


class VisualizationConfig(SlugModel):
    title = models.CharField(max_length=128, validators=[validate_name])
    configuration = models.JSONField(blank=True, null=True)
    created_by = models.ForeignKey(
        User,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="created_visualization_configs",
    )
    data_entry = models.ForeignKey(
        DataEntry, on_delete=models.CASCADE, related_name="visualizations"
    )
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="visualizations")

    field_to_slug = "title"

    class Meta(BaseModel.Meta):
        constraints = (
            models.UniqueConstraint(
                fields=("group_id", "slug"),
                condition=models.Q(deleted_at__isnull=True),
                name="shared_data_visualizationconfig_unique_active_slug_by_group",
            ),
        )
        verbose_name_plural = "Visualization Configs"
        rules_permissions = {
            "change": perm_rules.allowed_to_change_visualization_config,
            "delete": perm_rules.allowed_to_delete_visualization_config,
            "view": perm_rules.allowed_to_view_visualization_config,
        }
