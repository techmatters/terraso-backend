import graphene
from django.core.exceptions import ValidationError
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import Group, Membership, User
from apps.graphql.exceptions import GraphQLValidationException

from .commons import BaseDeleteMutation


class MembershipNode(DjangoObjectType):
    id = graphene.ID(source='pk', required=True)

    class Meta:
        model = Membership
        filter_fields = {
            "group": ["exact"],
            "user": ["exact"],
            "user_role": ["exact"],
            "group__slug": ["icontains"],
            "user__email": ["icontains"],
        }
        fields = ("group", "user", "user_role")
        interfaces = (relay.Node,)


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
            membership = Membership()
            membership.user = User.objects.get(email=kwargs.pop("user_email"))
            membership.group = Group.objects.get(slug=kwargs.pop("group_slug"))

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
