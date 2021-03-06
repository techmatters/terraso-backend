import structlog
from django.db import models, transaction

from apps.core import permission_rules as perm_rules

from .commons import BaseModel, SlugModel, validate_name
from .groups import Group
from .users import User

logger = structlog.get_logger(__name__)


class Landscape(SlugModel):
    """
    This model represents a Landscape on Terraso platform.

    A Landscape is a socio-ecological system that consists of natural
    and/or human-modified ecosystems. Defined by its stakeholds, a
    Landscape usually has geographical boundaries. It may correspond to,
    or be a combination of, natural boundaries, distinct land features,
    socially defined areas such as indigenous territories, and/or
    jurisdictional and administrative boundaries. The boundaries of a
    Landscape can cross several countries.
    """

    fields_to_trim = ["name", "description"]

    name = models.CharField(max_length=128, unique=True, validators=[validate_name])
    description = models.TextField(blank=True, default="")
    website = models.URLField(blank=True, default="")
    location = models.CharField(max_length=128, blank=True, default="")
    area_polygon = models.JSONField(blank=True, null=True)

    created_by = models.ForeignKey(
        User,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="created_landscapes",
    )
    groups = models.ManyToManyField(Group, through="LandscapeGroup")

    field_to_slug = "name"

    class Meta(SlugModel.Meta):
        rules_permissions = {
            "change": perm_rules.allowed_to_change_landscape,
            "delete": perm_rules.allowed_to_delete_landscape,
        }

    def save(self, *args, **kwargs):
        with transaction.atomic():
            creating = not Landscape.objects.filter(pk=self.pk).exists()

            super().save(*args, **kwargs)

            if creating and self.created_by:
                group = Group(
                    name="Group {}".format(self.slug),
                    description="",
                    created_by=self.created_by,
                )
                group.save()
                landscape_group = LandscapeGroup(
                    group=group, landscape=self, is_default_landscape_group=True
                )
                landscape_group.save()

    def get_default_group(self):
        """
        A default Group in a Landscape is that Group where any
        individual (associated or not with other Groups) is added when
        associating directly with a Landscape.
        """
        try:
            # associated_groups is the related_name defined on
            # LandscapeGroup relationship with Landscape. It returns a
            # queryset of LandscapeGroup
            landscape_group = self.associated_groups.get(is_default_landscape_group=True)
        except LandscapeGroup.DoesNotExist:
            logger.error(
                "Landscape has no default group, but it must have", extra={"landscape_id": self.pk}
            )
            return None

        return landscape_group.group

    def __str__(self):
        return self.name


class LandscapeGroup(BaseModel):
    """
    This model represents the association between a Landscape and a Group on
    Terraso platform.
    """

    landscape = models.ForeignKey(
        Landscape, on_delete=models.CASCADE, related_name="associated_groups"
    )
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="associated_landscapes")

    is_default_landscape_group = models.BooleanField(blank=True, default=False)

    class Meta:
        rules_permissions = {
            "add": perm_rules.allowed_to_add_landscape_group,
            "delete": perm_rules.allowed_to_delete_landscape_group,
        }
        constraints = (
            models.UniqueConstraint(
                fields=("group", "landscape"),
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_landscape_group",
            ),
        )
