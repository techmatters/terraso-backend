# Copyright © 2023 Technology Matters
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

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from safedelete.models import SafeDeleteManager

from apps.core.models import BaseModel, User


class MembershipList(BaseModel):
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

    enroll_method = models.CharField(
        max_length=10, choices=ENROLL_METHODS, default=DEFAULT_ENROLL_METHOD_TYPE
    )

    members = models.ManyToManyField(User, through="Membership")

    membership_type = models.CharField(
        max_length=32,
        choices=MEMBERSHIP_TYPES,
        default=DEFAULT_MEMERBSHIP_TYPE,
    )

    def save_membership(self, user_email, user_role, membership_status, validation_func):
        user = User.objects.filter(email=user_email).first()
        user_exists = user is not None

        membership = self.get_membership(user)
        is_new = not membership

        previous_membership_status = membership.membership_status if not is_new else None

        if validation_func(
            {
                "user_role": user_role,
                "membership_status": membership_status,
                "current_membership": membership,
            }
        ):
            raise ValidationError("User cannot request membership")

        if is_new:
            membership = Membership(
                membership_list=self,
                user=user if user_exists else None,
                pending_email=user_email if not user_exists else None,
                user_role=user_role,
                membership_status=membership_status,
            )
        else:
            membership.user_role = user_role
            if membership_status:
                membership.membership_status = membership_status

        membership_status = membership.membership_status

        is_membership_approved = (
            previous_membership_status is not None
            and previous_membership_status != Membership.APPROVED
            and membership_status == Membership.APPROVED
        )

        membership.save()
        return is_membership_approved, membership

    def approve_membership(self, membership_id):
        membership = self.memberships.filter(id=membership_id).first()
        if not membership:
            raise ValidationError("Membership not found")

        if membership.membership_status == Membership.APPROVED:
            return membership

        membership.membership_status = Membership.APPROVED
        membership.save()
        return membership

    @property
    def approved_members(self):
        approved_memberships_user_ids = models.Subquery(
            self.memberships.approved_only().values("user_id")
        )
        return User.objects.filter(id__in=approved_memberships_user_ids)

    def has_role(self, user: User, role: str) -> bool:
        return self.memberships.by_role(role).filter(id=user.id).exists()

    def is_approved_member(self, user: User) -> bool:
        return self.approved_members.filter(id=user.id).exists()

    def is_member(self, user: User) -> bool:
        return self.members.filter(id=user.id).exists()

    def get_membership(self, user: User):
        return self.memberships.filter(user=user).first()

    @property
    def can_join(self):
        return self.enroll_method in (self.ENROLL_METHOD_JOIN, self.ENROLL_METHOD_BOTH)

    @classmethod
    def get_membership_type_from_text(cls, membership_type):
        if membership_type and membership_type.lower() == cls.MEMBERSHIP_TYPE_CLOSED:
            return cls.MEMBERSHIP_TYPE_CLOSED
        return cls.MEMBERSHIP_TYPE_OPEN


class MembershipObjectsManager(SafeDeleteManager):
    def by_role(self, role):
        return self.filter(user_role=role, membership_status=Membership.APPROVED)

    def approved_only(self):
        return self.filter(membership_status=Membership.APPROVED)


class Membership(BaseModel):
    APPROVED = "approved"
    PENDING = "pending"

    APPROVAL_STATUS = (
        (APPROVED, _("Approved")),
        (PENDING, _("Pending")),
    )

    membership_list = models.ForeignKey(
        MembershipList, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="collaboration_memberships", null=True
    )

    user_role = models.CharField(max_length=64)

    membership_status = models.CharField(max_length=64, choices=APPROVAL_STATUS, default=APPROVED)

    pending_email = models.EmailField(null=True, blank=True)

    objects = MembershipObjectsManager()

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("membership_list", "user"),
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_collaboration_membership",
            ),
        )

    @classmethod
    def get_membership_status_from_text(cls, membership_status):
        if membership_status and membership_status.lower() == cls.APPROVED:
            return cls.APPROVED
        return cls.PENDING
