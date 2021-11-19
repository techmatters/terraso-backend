from django.db import models

from .commons import BaseModel, SlugModel
from .groups import Group


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

    name = models.CharField(max_length=128, unique=True)
    description = models.TextField(max_length=512, blank=True, default="")
    website = models.URLField(blank=True, default="")
    location = models.CharField(max_length=128, blank=True, default="")

    groups = models.ManyToManyField(Group, through="LandscapeGroup")

    field_to_slug = "name"

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
