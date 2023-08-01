from django.db import models
from django.utils.translation import gettext_lazy as _
from safedelete.models import SafeDeleteManager

from apps.core.models import BaseModel, User
from apps.notifications.email import EmailNotification


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

    def save_member(self, kwargs):
        user = kwargs["user"]
        user_role = kwargs["user_role"]
        membership_status = kwargs["membership_status"]

        membership = self.get_membership(user)
        is_closed = self.membership_type == MembershipList.MEMBERSHIP_TYPE_CLOSED
        is_new = not membership
        if is_new:
            membership = Membership(
                membership_list=self,
                user=user,
                user_role=user_role,
                membership_status=Membership.PENDING if is_closed else Membership.APPROVED,
            )
        else:
            previous_membership_status = membership.membership_status
            membership.user_role = user_role
            if membership_status:
                membership.membership_status = Membership.get_membership_status_from_text(
                    membership_status
                )

        membership_status = membership.membership_status

        is_membership_approved = (
            previous_membership_status != Membership.APPROVED
            and membership_status == Membership.APPROVED
        )

        if is_membership_approved:
            EmailNotification.send_membership_approval(membership.user, membership.membership_list)

        membership.save()
        return membership

    @property
    def approved_members(self):
        member_memberships = models.Subquery(self.memberships.approved_only().values("user_id"))
        return User.objects.filter(id__in=member_memberships)

    def has_role(self, user: User, role: str) -> bool:
        return self.memberships.by_role(role).filter(id=user.id).exists()

    def is_member(self, user: User) -> bool:
        return self.approved_members.filter(id=user.id).exists()

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
        User, on_delete=models.CASCADE, related_name="collaboration_memberships"
    )

    user_role = models.CharField(max_length=64)

    membership_status = models.CharField(max_length=64, choices=APPROVAL_STATUS, default=APPROVED)

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
