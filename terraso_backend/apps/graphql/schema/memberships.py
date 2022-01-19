import graphene
from django.conf import settings
from django.core.exceptions import ValidationError
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


class MembershipWriteMutation(relay.ClientIDMutation):
    membership = graphene.Field(MembershipNode)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        """
        This is the method performed everytime this mutation is submitted.
        Since this is the base class for write operations, this method will be
        called both when adding and updating Memberships. The `kwargs` receives
        a dictionary with all inputs informed.
        """
        _id = kwargs.pop("id", None)

        if _id:
            membership = Membership.objects.get(pk=_id)
        else:
            group = Group.objects.get(slug=kwargs.pop("group_slug"))
            user = User.objects.get(email=kwargs.pop("user_email"))
            membership, _ = Membership.objects.get_or_create(user=user, group=group)

        membership.user_role = Membership.get_user_role_from_text(kwargs.pop("user_role", None))

        try:
            membership.full_clean()
        except ValidationError as exc:
            raise GraphQLValidationException.from_validation_error(exc)

        membership.save()

        return cls(membership=membership)


class MembershipAddMutation(MembershipWriteMutation):
    class Input:
        user_email = graphene.String(required=True)
        group_slug = graphene.String(required=True)
        user_role = graphene.String()


class MembershipUpdateMutation(MembershipWriteMutation):
    class Input:
        id = graphene.ID(required=True)
        user_role = graphene.String(required=True)


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

        return super().mutate_and_get_payload(root, info, **kwargs)
