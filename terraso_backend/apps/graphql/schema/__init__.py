# Copyright © 2021-2023 Technology Matters
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see https://www.gnu.org/licenses/.

import graphene
from graphene_django.filter import DjangoFilterConnectionField

from .audit_logs import AuditLogNode
from .commons import TerrasoRelayNode
from .data_entries import (
    DataEntryAddMutation,
    DataEntryDeleteMutation,
    DataEntryNode,
    DataEntryUpdateMutation,
)
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
from .projects import ProjectAddMutation, ProjectDeleteMutation, ProjectUpdateMutation
from .sites import SiteAddMutation, SiteUpdateMutation, SiteNode
from .story_maps import StoryMapDeleteMutation, StoryMapNode
from .taxnomy_terms import TaxonomyTermNode
from .users import (
    UserAddMutation,
    UserDeleteMutation,
    UserNode,
    UserPreferenceDelete,
    UserPreferenceUpdate,
    UserUnsubscribeUpdate,
    UserUpdateMutation,
)
from .visualization_config import (
    VisualizationConfigAddMutation,
    VisualizationConfigDeleteMutation,
    VisualizationConfigNode,
    VisualizationConfigUpdateMutation,
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
    visualization_config = TerrasoRelayNode.Field(VisualizationConfigNode)
    visualization_configs = DjangoFilterConnectionField(VisualizationConfigNode)
    taxonomy_term = TerrasoRelayNode.Field(TaxonomyTermNode)
    taxonomy_terms = DjangoFilterConnectionField(TaxonomyTermNode)
    story_map = TerrasoRelayNode.Field(StoryMapNode)
    story_maps = DjangoFilterConnectionField(StoryMapNode)
    sites = DjangoFilterConnectionField(SiteNode)
    audit_logs = DjangoFilterConnectionField(AuditLogNode)


# All mutations should inherit from BaseWriteMutation or BaseDeleteMutation
# See terraso_backend/apps/graphql/schema/commons.py
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
    unsubscribe_user = UserUnsubscribeUpdate.Field()
    add_data_entry = DataEntryAddMutation.Field()
    update_data_entry = DataEntryUpdateMutation.Field()
    delete_data_entry = DataEntryDeleteMutation.Field()
    add_visualization_config = VisualizationConfigAddMutation.Field()
    update_visualization_config = VisualizationConfigUpdateMutation.Field()
    delete_visualization_config = VisualizationConfigDeleteMutation.Field()
    delete_story_map = StoryMapDeleteMutation.Field()
    add_site = SiteAddMutation.Field()
    edit_site = SiteUpdateMutation.Field()
    add_project = ProjectAddMutation.Field()
    delete_project = ProjectDeleteMutation.Field()
    edit_project = ProjectUpdateMutation.Field()


schema = graphene.Schema(query=Query, mutation=Mutations)
