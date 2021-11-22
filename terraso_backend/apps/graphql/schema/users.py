from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import User


class UserNode(DjangoObjectType):
    class Meta:
        model = User
        filter_fields = {
            "email": ["icontains"],
            "first_name": ["icontains"],
            "last_name": ["icontains"],
        }
        interfaces = (relay.Node,)
