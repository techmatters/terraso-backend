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
from typing import Literal, Union

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _

from apps.core import group_collaboration_roles
from apps.core import permission_rules as perm_rules

from .commons import BaseModel, SlugModel, validate_name
from .shared_resources import SharedResource
from .users import User


class Group(SlugModel):
    """
    This model represents a Group of individuals on Terraso platform.

    One of the key aspects of the Landscape Management is its nature of
    relation among multiple stakeholders. These stakeholders are usually
    organized in groups (formal or informal). Some examples of groups
    involved in Landscape Management are: non-government organizations,
    Landscape Partnerships, government entities, indigenous groups,
    research groups, etc.

    A Group might have other subgroups associated. This association, on
    Terraso backend platform is made by the GroupAssociation model.
    """

    MEMBERSHIP_TYPE_OPEN = "open"
    MEMBERSHIP_TYPE_CLOSED = "closed"
    DEFAULT_MEMERBSHIP_TYPE = MEMBERSHIP_TYPE_OPEN

    MEMBERSHIP_TYPES = (
        (MEMBERSHIP_TYPE_OPEN, _("Open")),
        (MEMBERSHIP_TYPE_CLOSED, _("Closed")),
    )

    ENROLL_METHOD_JOIN = "join"
    ENROLL_METHOD_INVITE = "invite"
    ENROLL_METHOD_BOTH = "both"
    DEFAULT_ENROLL_METHOD_TYPE = ENROLL_METHOD_JOIN

    ENROLL_METHODS = (
        (ENROLL_METHOD_JOIN, _("Join")),
        (ENROLL_METHOD_INVITE, _("Invite")),
        (ENROLL_METHOD_BOTH, _("Both")),
    )

    fields_to_trim = ["name", "description"]

    name = models.CharField(max_length=128, validators=[validate_name])
    description = models.TextField(max_length=2048, blank=True, default="")
    website = models.URLField(max_length=500, blank=True, default="")
    email = models.EmailField(blank=True, default="")

    enroll_method = models.CharField(
        max_length=10, choices=ENROLL_METHODS, default=DEFAULT_ENROLL_METHOD_TYPE
    )

    created_by = models.ForeignKey(
        User,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="created_groups",
    )

    # Symmetrical=False is necessary so Group A being parent of Group B
    # doesn't make Django assume Group B is also parent of Group A
    group_associations = models.ManyToManyField(
        "self",
        through="GroupAssociation",
        through_fields=("parent_group", "child_group"),
        symmetrical=False,
    )

    # Deprecated memberships fields
    # members = models.ManyToManyField(User, through="Membership")
    # membership_type = models.CharField(
    #     max_length=32,
    #     choices=MEMBERSHIP_TYPES,
    #     default=DEFAULT_MEMERBSHIP_TYPE,
    # )
    # End of deprecated fields

    membership_list = models.ForeignKey(
        "collaboration.MembershipList",
        on_delete=models.CASCADE,
        related_name="group",
        null=True,
    )

    shared_resources = GenericRelation(
        SharedResource, content_type_field="target_content_type", object_id_field="target_object_id"
    )

    field_to_slug = "name"

    class Meta(SlugModel.Meta):
        rules_permissions = {
            "change": perm_rules.allowed_to_change_group,
            "delete": perm_rules.allowed_to_delete_group,
        }
        _unique_fields = ["name"]

    def full_clean(self, *args, **kwargs):
        super().full_clean(*args, **kwargs, exclude=["membership_list"])

    def save(self, *args, **kwargs):
        with transaction.atomic():
            from apps.collaboration.models import Membership, MembershipList

            creating = not Group.objects.filter(pk=self.pk).exists()

            if creating and self.created_by:
                self.membership_list = MembershipList.objects.create(
                    enroll_method=MembershipList.ENROLL_METHOD_BOTH,
                    membership_type=MembershipList.MEMBERSHIP_TYPE_OPEN,
                )
                self.membership_list.save_membership(
                    self.created_by.email,
                    group_collaboration_roles.ROLE_MANAGER,
                    Membership.APPROVED,
                )

            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        membership_list = self.membership_list

        with transaction.atomic():
            ret = super().delete(*args, **kwargs)
            if membership_list is not None:
                membership_list.delete()

        return ret

    def add_manager(self, user):
        self._add_user(user, role=group_collaboration_roles.ROLE_MANAGER)

    def add_member(self, user):
        self._add_user(user, role=group_collaboration_roles.ROLE_MEMBER)

    def _add_user(
        self,
        user: User,
        role: Union[Literal["manager"], Literal["member"]],
    ):
        from apps.collaboration.models import Membership

        self.membership_list.save_membership(
            user.email,
            role,
            Membership.APPROVED,
        )

    def __str__(self):
        return self.name


class GroupAssociation(BaseModel):
    """
    This model represents a association of Groups on Terraso platform.
    More specifically, this association between groups can be
    interpreted as Group -> Subgroup association.
    """

    parent_group = models.ForeignKey(
        Group, on_delete=models.CASCADE, related_name="associations_as_parent"
    )
    child_group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="associations_as_child",
    )

    class Meta:
        rules_permissions = {
            "add": perm_rules.allowed_to_add_group_association,
            "delete": perm_rules.allowed_to_delete_group_association,
        }
        constraints = (
            models.UniqueConstraint(
                fields=("parent_group", "child_group"),
                condition=models.Q(deleted_at__isnull=True),
                name="unique_group_association",
            ),
        )


class Membership(BaseModel):
    """
    This model represents the association between a User and a Group on
    Terraso platform.

    Each User may have different roles on each associated Group. So,
    this model also stores the specific role of a given User in a
    specific Group.
    """

    ROLE_MANAGER = "manager"
    ROLE_MEMBER = "member"
    ROLES = (
        (ROLE_MANAGER, _("Manager")),
        (ROLE_MEMBER, _("Member")),
    )

    APPROVED = "approved"
    PENDING = "pending"

    APPROVAL_STATUS = (
        (APPROVED, _("Approved")),
        (PENDING, _("Pending")),
    )

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")

    user_role = models.CharField(max_length=64, choices=ROLES, default=ROLE_MEMBER)

    membership_status = models.CharField(max_length=64, choices=APPROVAL_STATUS, default=APPROVED)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("group", "user"),
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_membership",
            ),
        )

    @classmethod
    def get_user_role_from_text(cls, user_role):
        if user_role and user_role.lower() == cls.ROLE_MANAGER:
            return cls.ROLE_MANAGER

        return cls.ROLE_MEMBER

    @classmethod
    def get_membership_status_from_text(cls, membership_status):
        if membership_status and membership_status.lower() == cls.APPROVED:
            return cls.APPROVED
        return cls.PENDING
