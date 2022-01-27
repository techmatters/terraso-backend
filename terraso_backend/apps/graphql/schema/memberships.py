import graphene
import rules
from django.conf import settings
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import Group, Membership, User
from apps.graphql.exceptions import GraphQLValidationException

from .commons import BaseDeleteMutation, TerrasoConnection


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
        try:
            user = User.objects.get(email=kwargs.pop("user_email"))
        except User.DoesNotExist:
            raise GraphQLValidationException("User not found.")

        try:
            group = Group.objects.get(slug=kwargs.pop("group_slug"))
        except Group.DoesNotExist:
            raise GraphQLValidationException("Group not found.")

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
        if not settings.FEATURE_FLAGS["CHECK_PERMISSIONS"]:
            return super().mutate_and_get_payload(root, info, **kwargs)

        user = info.context.user

        try:
            membership = Membership.objects.get(pk=kwargs["id"])
        except Membership.DoesNotExist:
            raise GraphQLValidationException("Membership not found.")

        user_role = kwargs.pop("user_role", None)
        if not user_role:
            return cls(membership=membership)

        if not user.has_perm(Membership.get_perm("change"), obj=membership.group.id):
            raise GraphQLValidationException("User has no permission to change Membership.")

        if not rules.test_rule("allowed_group_managers_count", user, kwargs["id"]):
            raise GraphQLValidationException("A Group needs to have at least one manager.")

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

        if not settings.FEATURE_FLAGS["CHECK_PERMISSIONS"]:
            return super().mutate_and_get_payload(root, info, **kwargs)

        if not user.has_perm(Membership.get_perm("delete"), obj=kwargs["id"]):
            raise GraphQLValidationException("User has no permission to delete Membership.")

        if not rules.test_rule("allowed_group_managers_count", user, kwargs["id"]):
            raise GraphQLValidationException("A Group needs to have at least one manager.")

        return super().mutate_and_get_payload(root, info, **kwargs)
