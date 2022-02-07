import graphene
import rules
import structlog
from django.conf import settings
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
        }
        fields = ("group", "user", "user_role")
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection


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

        membership.user_role = user_role
        membership.save()

        return cls(membership=membership)


class MembershipUpdateMutation(relay.ClientIDMutation):
    membership = graphene.Field(MembershipNode)

    class Input:
        id = graphene.ID(required=True)
        user_role = graphene.String(required=True)

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

        user_role = kwargs.pop("user_role", None)
        if not user_role:
            return cls(membership=membership)

        ff_check_permission_on = settings.FEATURE_FLAGS["CHECK_PERMISSIONS"]

        if ff_check_permission_on and not user.has_perm(
            Membership.get_perm("change"), obj=membership.group.id
        ):
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

        membership.user_role = Membership.get_user_role_from_text(user_role)
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

        if not settings.FEATURE_FLAGS["CHECK_PERMISSIONS"]:
            return super().mutate_and_get_payload(root, info, **kwargs)

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
