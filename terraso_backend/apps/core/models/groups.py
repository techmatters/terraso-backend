from django.db import models, transaction
from django.utils.translation import gettext_lazy as _

from apps.core import permission_rules as perm_rules

from .commons import BaseModel, SlugModel
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

    name = models.CharField(max_length=128, unique=True)
    description = models.TextField(max_length=512, blank=True, default="")
    website = models.URLField(blank=True, default="")
    email = models.EmailField(blank=True, default="")

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

    field_to_slug = "name"

    class Meta:
        rules_permissions = {
            "change": perm_rules.is_group_manager,
        }

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
        self.memberships.update_or_create(
            group=self, user=user, defaults={"user_role": Membership.ROLE_MANAGER}
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
        constraints = (
            models.UniqueConstraint(
                fields=("parent_group", "child_group"),
                name="unique_group_association",
            ),
        )


class MembershipManager(models.Manager):
    def managers_only(self):
        return self.filter(user_role=Membership.ROLE_MANAGER)


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

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")

    user_role = models.CharField(max_length=64, choices=ROLES, blank=True, default=ROLE_MEMBER)

    objects = MembershipManager()

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("group", "user"),
                name="unique_membership",
            ),
        )

    @classmethod
    def get_user_role_from_text(cls, user_role):
        if user_role and user_role.lower() == cls.ROLE_MANAGER:
            return cls.ROLE_MANAGER

        return cls.ROLE_MEMBER
