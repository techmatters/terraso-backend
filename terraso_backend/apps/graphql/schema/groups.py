from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField

from apps.core.models import Group, GroupAssociation, Membership


class GroupAssociationNode(DjangoObjectType):
    class Meta:
        model = GroupAssociation
        filter_fields = ["parent_group", "child_group"]
        interfaces = (relay.Node,)


class MembershipNode(DjangoObjectType):
    class Meta:
        model = Membership
        filter_fields = ["group", "user", "user_role"]
        interfaces = (relay.Node,)


class GroupNode(DjangoObjectType):
    associations_as_parent = DjangoFilterConnectionField(GroupAssociationNode)
    associations_as_child = DjangoFilterConnectionField(GroupAssociationNode)
    memberships = DjangoFilterConnectionField(MembershipNode)

    class Meta:
        model = Group
        filter_fields = {
            "name": ["exact", "icontains", "istartswith"],
            "slug": ["icontains"],
            "description": ["icontains"],
            "associations_as_parent": ["exact"],
            "associations_as_child": ["exact"],
            "members__email": ["icontains"],
            "memberships": ["exact"],
        }
        interfaces = (relay.Node,)

    def resolve_associations_as_parent(self, info):
        return self.associations_as_parent.all()

    def resolve_associations_as_child(self, info):
        return self.associations_as_child.all()
