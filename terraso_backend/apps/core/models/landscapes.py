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

import structlog
from dirtyfields import DirtyFieldsMixin
from django.apps import apps
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models, transaction

from apps.core import permission_rules as perm_rules
from apps.core.gis.utils import (
    calculate_geojson_centroid,
    calculate_geojson_feature_area,
)
from apps.core.landscape_collaboration_roles import ROLE_MANAGER
from apps.core.models.taxonomy_terms import TaxonomyTerm

from .commons import BaseModel, SlugModel, validate_name
from .groups import Group
from .shared_resources import SharedResource
from .users import User

logger = structlog.get_logger(__name__)


class Landscape(SlugModel, DirtyFieldsMixin):
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

    name = models.CharField(max_length=128, validators=[validate_name])
    description = models.TextField(blank=True, default="")
    website = models.URLField(max_length=500, blank=True, default="")
    location = models.CharField(max_length=128, blank=True, default="")
    area_polygon = models.JSONField(blank=True, null=True)
    email = models.EmailField(blank=True, default="")
    area_scalar_m2 = models.FloatField(blank=True, null=True)

    created_by = models.ForeignKey(
        User,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="created_landscapes",
    )
    groups = models.ManyToManyField(Group, through="LandscapeGroup")
    membership_list = models.ForeignKey(
        "collaboration.MembershipList",
        on_delete=models.CASCADE,
        related_name="landscape",
        null=True,
    )

    area_types = models.JSONField(blank=True, null=True)
    taxonomy_terms = models.ManyToManyField(TaxonomyTerm, blank=True)
    population = models.IntegerField(blank=True, null=True)

    PARTNERSHIP_STATUS_NONE = ""
    PARTNERSHIP_STATUS_NO = "no"
    PARTNERSHIP_STATUS_IN_PROGRESS = "in-progress"
    PARTNERSHIP_STATUS_YES = "yes"

    MEMBERSHIP_TYPES = (
        (PARTNERSHIP_STATUS_NONE, "None"),
        (PARTNERSHIP_STATUS_NO, "No"),
        (PARTNERSHIP_STATUS_IN_PROGRESS, "In Progress"),
        (PARTNERSHIP_STATUS_YES, "Yes"),
    )
    partnership_status = models.CharField(
        max_length=32, choices=MEMBERSHIP_TYPES, blank=True, default=PARTNERSHIP_STATUS_NONE
    )
    profile_image = models.URLField(blank=True, default="")
    profile_image_description = models.TextField(blank=True, default="")
    center_coordinates = models.JSONField(blank=True, null=True)

    shared_resources = GenericRelation(
        SharedResource, content_type_field="target_content_type", object_id_field="target_object_id"
    )

    field_to_slug = "name"

    class Meta(SlugModel.Meta):
        rules_permissions = {
            "change": perm_rules.allowed_to_change_landscape,
            "delete": perm_rules.allowed_to_delete_landscape,
        }
        _unique_fields = ["name"]
        abstract = False

    def full_clean(self, *args, **kwargs):
        super().full_clean(*args, **kwargs, exclude=["membership_list"])

    def save(self, *args, **kwargs):
        dirty_fields = self.get_dirty_fields()
        if self.area_polygon and "area_polygon" in dirty_fields:
            area_scalar_m2 = calculate_geojson_feature_area(self.area_polygon)
            if area_scalar_m2 is not None:
                self.area_scalar_m2 = round(area_scalar_m2, 3)
            self.center_coordinates = calculate_geojson_centroid(self.area_polygon)

        with transaction.atomic():
            MembershipList = apps.get_model("collaboration", "MembershipList")
            Membership = apps.get_model("collaboration", "Membership")
            creating = not Landscape.objects.filter(pk=self.pk).exists()

            if creating and self.created_by:
                self.membership_list = MembershipList.objects.create(
                    enroll_method=MembershipList.ENROLL_METHOD_BOTH,
                    membership_type=MembershipList.MEMBERSHIP_TYPE_OPEN,
                )
                self.membership_list.save_membership(
                    self.created_by.email, ROLE_MANAGER, Membership.APPROVED
                )

            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        membership_list = self.membership_list

        with transaction.atomic():
            ret = super().delete(*args, **kwargs)
            if membership_list is not None:
                membership_list.delete()

        return ret

    def __str__(self):
        return self.name


class LandscapeDevelopmentStrategy(BaseModel):
    objectives = models.TextField(blank=True, default="")
    opportunities = models.TextField(blank=True, default="")
    problem_situtation = models.TextField(blank=True, default="")
    intervention_strategy = models.TextField(blank=True, default="")
    landscape = models.ForeignKey(
        Landscape, on_delete=models.CASCADE, related_name="associated_development_strategy"
    )


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
    is_partnership = models.BooleanField(blank=True, default=False)
    partnership_year = models.IntegerField(blank=True, null=True)

    class Meta:
        rules_permissions = {
            "add": perm_rules.allowed_to_add_landscape_group,
            "delete": perm_rules.allowed_to_delete_landscape_group,
        }
        constraints = (
            models.UniqueConstraint(
                fields=("group", "landscape", "is_partnership"),
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_landscape_group",
            ),
        )
