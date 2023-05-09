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

from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from safedelete.models import SafeDeleteManager

from apps.core import permission_rules as perm_rules

from .commons import BaseModel, SlugModel, validate_name
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
    members = models.ManyToManyField(User, through="Membership")

    membership_type = models.CharField(
        max_length=32,
        choices=MEMBERSHIP_TYPES,
        default=DEFAULT_MEMERBSHIP_TYPE,
    )

    field_to_slug = "name"

    class Meta(SlugModel.Meta):
        rules_permissions = {
            "change": perm_rules.allowed_to_change_group,
            "delete": perm_rules.allowed_to_delete_group,
        }
        _unique_fields = ["name"]

    def save(self, *args, **kwargs):
        with transaction.atomic():
            creating = not Group.objects.filter(pk=self.pk).exists()

            super().save(*args, **kwargs)

            if creating and self.created_by:
                membership = Membership(
                    group=self,
                    user=self.created_by,
                    user_role=Membership.ROLE_MANAGER,
                )
                membership.save()

    def add_manager(self, user):
        self._add_user(user, role=Membership.ROLE_MANAGER)

    def add_member(self, user):
        self._add_user(user, role=Membership.ROLE_MEMBER)

    def _add_user(
        self,
        user: User,
        role: Union[Literal["manager"], Literal["member"]],
    ):
        self.memberships.update_or_create(group=self, user=user, defaults={"user_role": role})

    @property
    def group_managers(self):
        manager_memberships = models.Subquery(self.memberships.managers_only().values("user_id"))
        return User.objects.filter(id__in=manager_memberships)

    @property
    def group_members(self):
        member_memberships = models.Subquery(
            self.memberships.approved_only()
            .filter(user_role=Membership.ROLE_MEMBER)
            .values("user_id")
        )
        return User.objects.filter(id__in=member_memberships)

    def is_manager(self, user: User) -> bool:
        return self.group_managers.filter(id=user.id).exists()

    def is_member(self, user: User) -> bool:
        return self.group_members.filter(id=user.id).exists()

    @property
    def can_join(self):
        return self.enroll_method in (self.ENROLL_METHOD_JOIN, self.ENROLL_METHOD_BOTH)

    def __str__(self):
        return self.name

    @classmethod
    def get_membership_type_from_text(cls, membership_type):
        if membership_type and membership_type.lower() == cls.MEMBERSHIP_TYPE_CLOSED:
            return cls.MEMBERSHIP_TYPE_CLOSED
        return cls.MEMBERSHIP_TYPE_OPEN


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


class MembershipObjectsManager(SafeDeleteManager):
    def managers_only(self):
        return self.filter(user_role=Membership.ROLE_MANAGER, membership_status=Membership.APPROVED)

    def approved_only(self):
        return self.filter(membership_status=Membership.APPROVED)


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

    user_role = models.CharField(max_length=64, choices=ROLES, blank=True, default=ROLE_MEMBER)

    membership_status = models.CharField(max_length=64, choices=APPROVAL_STATUS, default=APPROVED)

    objects = MembershipObjectsManager()

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("group", "user"),
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_membership",
            ),
        )
        rules_permissions = {
            "add": perm_rules.allowed_to_add_membership,
            "delete": perm_rules.allowed_to_delete_membership,
            "change": perm_rules.allowed_to_change_membership,
        }

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
