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

from apps.project_management.graphql.projects import (
    ProjectAddMutation,
    ProjectAddUserMutation,
    ProjectArchiveMutation,
    ProjectDeleteMutation,
    ProjectDeleteUserMutation,
    ProjectMarkSeenMutation,
    ProjectNode,
    ProjectUpdateMutation,
    ProjectUpdateUserRoleMutation,
)
from apps.project_management.graphql.site_notes import (
    SiteNoteAddMutation,
    SiteNoteDeleteMutation,
    SiteNoteUpdateMutation,
)
from apps.soil_id.graphql.soil_data.mutations import (
    DepthDependentSoilDataUpdateMutation,
    SoilDataDeleteDepthIntervalMutation,
    SoilDataUpdateDepthIntervalMutation,
    SoilDataUpdateMutation,
)
from apps.soil_id.graphql.soil_data.push_mutation import SoilDataPush
from apps.soil_id.graphql.soil_id.queries import soil_id
from apps.soil_id.graphql.soil_metadata.mutations import SoilMetadataUpdateMutation
from apps.soil_id.graphql.soil_project.mutations import (
    ProjectSoilSettingsDeleteDepthIntervalMutation,
    ProjectSoilSettingsUpdateDepthIntervalMutation,
    ProjectSoilSettingsUpdateMutation,
)

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
from .groups_memberships import (
    GroupMembershipDeleteMutation,
    GroupMembershipSaveMutation,
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
from .landscapes_memberships import (
    LandscapeMembershipDeleteMutation,
    LandscapeMembershipSaveMutation,
)
from .shared_resources import SharedResourceRelayNode, SharedResourceUpdateMutation
from .sites import (
    SiteAddMutation,
    SiteDeleteMutation,
    SiteMarkSeenMutation,
    SiteNode,
    SiteTransferMutation,
    SiteUpdateMutation,
)
from .story_maps import StoryMapDeleteMutation, StoryMapNode
from .story_maps_memberships import (
    StoryMapMembershipApproveMutation,
    StoryMapMembershipApproveTokenMutation,
    StoryMapMembershipDeleteMutation,
    StoryMapMembershipSaveMutation,
)
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
    group_association = TerrasoRelayNode.Field(GroupAssociationNode)
    groups = DjangoFilterConnectionField(GroupNode)
    landscapes = DjangoFilterConnectionField(LandscapeNode)
    landscape_groups = DjangoFilterConnectionField(LandscapeGroupNode)
    users = DjangoFilterConnectionField(UserNode)
    landscape_groups = DjangoFilterConnectionField(LandscapeGroupNode)
    group_associations = DjangoFilterConnectionField(GroupAssociationNode)
    data_entry = TerrasoRelayNode.Field(DataEntryNode)
    data_entries = DjangoFilterConnectionField(DataEntryNode)
    visualization_config = TerrasoRelayNode.Field(VisualizationConfigNode)
    visualization_configs = DjangoFilterConnectionField(VisualizationConfigNode)
    taxonomy_term = TerrasoRelayNode.Field(TaxonomyTermNode)
    taxonomy_terms = DjangoFilterConnectionField(TaxonomyTermNode)
    story_map = TerrasoRelayNode.Field(StoryMapNode)
    story_maps = DjangoFilterConnectionField(StoryMapNode)
    project = TerrasoRelayNode.Field(ProjectNode)
    projects = DjangoFilterConnectionField(ProjectNode, required=True)
    site = TerrasoRelayNode.Field(SiteNode)
    sites = DjangoFilterConnectionField(SiteNode, required=True)
    shared_resource = SharedResourceRelayNode.Field()
    soil_id = soil_id
    from .shared_resources import resolve_shared_resource


# All mutations should inherit from BaseWriteMutation or BaseDeleteMutation
# See terraso_backend/apps/graphql/schema/commons.py
class Mutations(graphene.ObjectType):
    add_group = GroupAddMutation.Field()
    add_landscape = LandscapeAddMutation.Field()
    add_user = UserAddMutation.Field()
    add_landscape_group = LandscapeGroupAddMutation.Field()
    add_group_association = GroupAssociationAddMutation.Field()
    update_group = GroupUpdateMutation.Field()
    update_landscape = LandscapeUpdateMutation.Field()
    update_user = UserUpdateMutation.Field()
    delete_group = GroupDeleteMutation.Field()
    delete_landscape = LandscapeDeleteMutation.Field()
    delete_user = UserDeleteMutation.Field()
    delete_landscape_group = LandscapeGroupDeleteMutation.Field()
    delete_group_association = GroupAssociationDeleteMutation.Field()
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
    save_story_map_membership = StoryMapMembershipSaveMutation.Field()
    delete_story_map_membership = StoryMapMembershipDeleteMutation.Field()
    approve_story_map_membership = StoryMapMembershipApproveMutation.Field()
    approve_story_map_membership_token = StoryMapMembershipApproveTokenMutation.Field()
    add_site = SiteAddMutation.Field()
    update_site = SiteUpdateMutation.Field()
    delete_site = SiteDeleteMutation.Field()
    mark_site_seen = SiteMarkSeenMutation.Field()
    transfer_sites = SiteTransferMutation.Field()
    add_project = ProjectAddMutation.Field()
    update_project = ProjectUpdateMutation.Field()
    archive_project = ProjectArchiveMutation.Field()
    delete_project = ProjectDeleteMutation.Field()
    add_user_to_project = ProjectAddUserMutation.Field()
    delete_user_from_project = ProjectDeleteUserMutation.Field()
    update_user_role_in_project = ProjectUpdateUserRoleMutation.Field()
    mark_project_seen = ProjectMarkSeenMutation.Field()
    update_soil_data = SoilDataUpdateMutation.Field(
        deprecation_reason="Use push_soil_data instead."
    )
    update_depth_dependent_soil_data = DepthDependentSoilDataUpdateMutation.Field(
        deprecation_reason="Use push_soil_data instead."
    )
    push_soil_data = SoilDataPush.Field()
    update_soil_data_depth_interval = SoilDataUpdateDepthIntervalMutation.Field(
        deprecation_reason="Use push_soil_data instead."
    )
    delete_soil_data_depth_interval = SoilDataDeleteDepthIntervalMutation.Field(
        deprecation_reason="Use push_soil_data instead."
    )
    update_soil_metadata = SoilMetadataUpdateMutation.Field()
    update_project_soil_settings = ProjectSoilSettingsUpdateMutation.Field()
    update_project_soil_settings_depth_interval = (
        ProjectSoilSettingsUpdateDepthIntervalMutation.Field()
    )
    delete_project_soil_settings_depth_interval = (
        ProjectSoilSettingsDeleteDepthIntervalMutation.Field()
    )
    add_site_note = SiteNoteAddMutation.Field()
    update_site_note = SiteNoteUpdateMutation.Field()
    delete_site_note = SiteNoteDeleteMutation.Field()
    save_landscape_membership = LandscapeMembershipSaveMutation.Field()
    delete_landscape_membership = LandscapeMembershipDeleteMutation.Field()
    save_group_membership = GroupMembershipSaveMutation.Field()
    delete_group_membership = GroupMembershipDeleteMutation.Field()
    update_shared_resource = SharedResourceUpdateMutation.Field()


schema = graphene.Schema(query=Query, mutation=Mutations)
