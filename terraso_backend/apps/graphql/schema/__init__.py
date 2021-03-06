import graphene
from graphene_django.filter import DjangoFilterConnectionField

from .commons import TerrasoRelayNode
from .group_associations import (
    GroupAssociationAddMutation,
    GroupAssociationDeleteMutation,
    GroupAssociationNode,
)
from .groups import (
    GroupAddMutation,
    GroupDeleteMutation,
    GroupNode,
    GroupUpdateMutation,
)
from .landscape_groups import (
    LandscapeGroupAddMutation,
    LandscapeGroupDeleteMutation,
    LandscapeGroupNode,
)
from .landscapes import (
    LandscapeAddMutation,
    LandscapeDeleteMutation,
    LandscapeNode,
    LandscapeUpdateMutation,
)
from .memberships import (
    MembershipAddMutation,
    MembershipDeleteMutation,
    MembershipNode,
    MembershipUpdateMutation,
)
from .shared_data import DataEntryDeleteMutation, DataEntryNode, DataEntryUpdateMutation
from .users import (
    UserAddMutation,
    UserDeleteMutation,
    UserNode,
    UserPreferenceDelete,
    UserPreferenceUpdate,
    UserUpdateMutation,
)


class Query(graphene.ObjectType):
    group = TerrasoRelayNode.Field(GroupNode)
    landscape = TerrasoRelayNode.Field(LandscapeNode)
    landscape_group = TerrasoRelayNode.Field(LandscapeNode)
    user = TerrasoRelayNode.Field(UserNode)
    landscape_group = TerrasoRelayNode.Field(LandscapeGroupNode)
    membership = TerrasoRelayNode.Field(MembershipNode)
    group_association = TerrasoRelayNode.Field(GroupAssociationNode)
    groups = DjangoFilterConnectionField(GroupNode)
    landscapes = DjangoFilterConnectionField(LandscapeNode)
    landscape_groups = DjangoFilterConnectionField(LandscapeGroupNode)
    users = DjangoFilterConnectionField(UserNode)
    landscape_groups = DjangoFilterConnectionField(LandscapeGroupNode)
    memberships = DjangoFilterConnectionField(MembershipNode)
    group_associations = DjangoFilterConnectionField(GroupAssociationNode)
    data_entry = TerrasoRelayNode.Field(DataEntryNode)
    data_entries = DjangoFilterConnectionField(DataEntryNode)


class Mutations(graphene.ObjectType):
    add_group = GroupAddMutation.Field()
    add_landscape = LandscapeAddMutation.Field()
    add_user = UserAddMutation.Field()
    add_landscape_group = LandscapeGroupAddMutation.Field()
    add_group_association = GroupAssociationAddMutation.Field()
    add_membership = MembershipAddMutation.Field()
    update_group = GroupUpdateMutation.Field()
    update_landscape = LandscapeUpdateMutation.Field()
    update_membership = MembershipUpdateMutation.Field()
    update_user = UserUpdateMutation.Field()
    delete_group = GroupDeleteMutation.Field()
    delete_landscape = LandscapeDeleteMutation.Field()
    delete_user = UserDeleteMutation.Field()
    delete_landscape_group = LandscapeGroupDeleteMutation.Field()
    delete_group_association = GroupAssociationDeleteMutation.Field()
    delete_membership = MembershipDeleteMutation.Field()
    update_user_preference = UserPreferenceUpdate.Field()
    delete_user_preference = UserPreferenceDelete.Field()
    update_data_entry = DataEntryUpdateMutation.Field()
    delete_data_entry = DataEntryDeleteMutation.Field()


schema = graphene.Schema(query=Query, mutation=Mutations)
