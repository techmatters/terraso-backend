from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel, User
from apps.shared_data import permission_rules as perm_rules

from .data_entries import DataEntry


class VisualizationConfig(BaseModel):
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

    class Meta(BaseModel.Meta):
        verbose_name_plural = "Visualization Configs"
        rules_permissions = {
            "change": perm_rules.allowed_to_change_visualization_config,
            "delete": perm_rules.allowed_to_delete_visualization_config,
            "view": perm_rules.allowed_to_view_visualization_config,
        }
