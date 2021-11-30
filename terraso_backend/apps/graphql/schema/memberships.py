from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import Membership


class MembershipNode(DjangoObjectType):
    class Meta:
        model = Membership
        filter_fields = ["group", "user", "user_role"]
        fields = ["group", "user", "user_role"]
        interfaces = (relay.Node,)
