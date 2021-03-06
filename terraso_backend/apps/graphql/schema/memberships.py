import graphene
import rules
import structlog
from django.db.models import Q
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import Group, Membership, User
from apps.graphql.exceptions import GraphQLNotAllowedException, GraphQLNotFoundException

from .commons import BaseDeleteMutation, TerrasoConnection
from .constants import MutationTypes

logger = structlog.get_logger(__name__)


class MembershipNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = Membership
        filter_fields = {
            "group": ["exact", "in"],
            "group__slug": ["icontains", "in"],
            "user": ["exact", "in"],
            "user_role": ["exact"],
            "user__email": ["icontains", "in"],
            "membership_status": ["exact"],
        }
        fields = ("group", "user", "user_role", "membership_status")
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection

    @classmethod
    def get_queryset(cls, queryset, info):
        user_groups_ids = Membership.objects.filter(
            user=info.context.user, membership_status=Membership.APPROVED
        ).values_list("group", flat=True)

        return queryset.filter(
            Q(group__membership_type=Group.MEMBERSHIP_TYPE_OPEN)
            | Q(group__in=user_groups_ids)
            | Q(user=info.context.user)
        )


class MembershipAddMutation(relay.ClientIDMutation):
    membership = graphene.Field(MembershipNode)

    class Input:
        user_email = graphene.String(required=True)
        group_slug = graphene.String(required=True)
        user_role = graphene.String()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user_email = kwargs.pop("user_email")
        group_slug = kwargs.pop("group_slug")

        try:
            user = User.objects.get(email=user_email)
        except User.DoesNotExist:
            logger.error(
                "User not found when adding a Membership",
                extra={"user_email": user_email},
            )
            raise GraphQLNotFoundException(field="user", model_name=Membership.__name__)

        try:
            group = Group.objects.get(slug=group_slug)
        except Group.DoesNotExist:
            logger.error(
                "Group not found when adding a Membership",
                extra={"group_slug": group_slug},
            )
            raise GraphQLNotFoundException(field="group", model_name=Membership.__name__)

        membership, was_created = Membership.objects.get_or_create(user=user, group=group)
        if was_created:
            user_role = Membership.get_user_role_from_text(kwargs.pop("user_role", None))
        else:
            user_role = Membership.get_user_role_from_text(
                kwargs.pop("user_role", membership.user_role)
            )

        if group.membership_type == Group.MEMBERSHIP_TYPE_CLOSED:
            membership.membership_status = Membership.PENDING

        membership.user_role = user_role
        membership.save()

        return cls(membership=membership)


class MembershipUpdateMutation(relay.ClientIDMutation):
    membership = graphene.Field(MembershipNode)

    class Input:
        id = graphene.ID(required=True)
        user_role = graphene.String()
        membership_status = graphene.String()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        membership_id = kwargs["id"]

        try:
            membership = Membership.objects.get(pk=membership_id)
        except Membership.DoesNotExist:
            logger.error(
                "Attempt to update a Membership, but it as not found",
                extra={"membership_id": membership_id},
            )
            raise GraphQLNotFoundException(model_name=Membership.__name__)

        if not user.has_perm(Membership.get_perm("change"), obj=membership.group.id):
            logger.info(
                "Attempt to update a Membership, but user has no permission",
                extra={"user_id": user.pk, "membership_id": membership_id},
            )
            raise GraphQLNotAllowedException(
                model_name=Membership.__name__, operation=MutationTypes.UPDATE
            )

        if not rules.test_rule("allowed_group_managers_count", user, kwargs["id"]):
            logger.info(
                "Attempt to update a Membership, but manager's count doesn't allow",
                extra={"user_id": user.pk, "membership_id": membership_id},
            )
            raise GraphQLNotAllowedException(
                model_name=Membership.__name__,
                operation=MutationTypes.UPDATE,
                message="manager_count",
            )

        user_role = kwargs.pop("user_role", None)
        if user_role:
            membership.user_role = Membership.get_user_role_from_text(user_role)
        membership_status = kwargs.pop("membership_status", None)
        if membership_status:
            membership.membership_status = Membership.get_membership_status_from_text(
                membership_status
            )
        membership.save()

        return cls(membership=membership)


class MembershipDeleteMutation(BaseDeleteMutation):
    membership = graphene.Field(MembershipNode)

    model_class = Membership

    class Input:
        id = graphene.ID()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        membership_id = kwargs["id"]

        if not user.has_perm(Membership.get_perm("delete"), obj=membership_id):
            logger.info(
                "Attempt to delete a Membership, but user has no permission",
                extra={"user_id": user.pk, "membership_id": membership_id},
            )
            raise GraphQLNotAllowedException(
                model_name=Membership.__name__, operation=MutationTypes.DELETE
            )

        if not rules.test_rule("allowed_group_managers_count", user, kwargs["id"]):
            logger.info(
                "Attempt to delete a Membership, but manager's count doesn't allow",
                extra={"user_id": user.pk, "membership_id": membership_id},
            )
            raise GraphQLNotAllowedException(
                model_name=Membership.__name__,
                operation=MutationTypes.DELETE,
                message="manager_count",
            )

        return super().mutate_and_get_payload(root, info, **kwargs)
