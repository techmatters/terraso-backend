import graphene
import graphql_relay
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import Group, Membership, User

from .commons import BaseDeleteMutation


class MembershipNode(DjangoObjectType):
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
        graphql_id = kwargs.pop("id", None)

        if graphql_id:
            _, _pk = graphql_relay.from_global_id(graphql_id)
            membership = Membership.objects.get(pk=_pk)
        else:
            membership = Membership()
            membership.user = User.objects.get(email=kwargs.pop("user_email"))
            membership.group = Group.objects.get(slug=kwargs.pop("group_slug"))

        membership.user_role = Membership.get_user_role_from_text(kwargs.pop("user_role", None))

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
