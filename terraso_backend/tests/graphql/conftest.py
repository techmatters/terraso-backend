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

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time
from graphene_django.utils.testing import graphql_query
from mixer.backend.django import mixer

from apps.auth.services import JWTService
from apps.collaboration.models import Membership as CollaborationMembership
from apps.collaboration.models import MembershipList
from apps.core import group_collaboration_roles, landscape_collaboration_roles
from apps.core.models import (
    Group,
    GroupAssociation,
    Landscape,
    LandscapeGroup,
    SharedResource,
    TaxonomyTerm,
    User,
    UserPreference,
)
from apps.core.models.users import (
    USER_PREFS_KEY_GROUP_NOTIFICATIONS,
    USER_PREFS_KEY_STORY_MAP_NOTIFICATIONS,
)
from apps.project_management.models import Site
from apps.shared_data.models import DataEntry, VisualizationConfig
from apps.soil_id.models import SoilData, SoilDataDepthInterval
from apps.story_map.models import StoryMap

pytestmark = pytest.mark.django_db


@pytest.fixture
def access_token(user):
    return JWTService().create_access_token(user)


@pytest.fixture
@freeze_time(timezone.now() - timedelta(days=10))
def expired_access_token(user):
    return JWTService().create_access_token(user)


@pytest.fixture
def client_query(client, access_token):
    def _client_query(*args, **kwargs):
        headers = {
            "CONTENT_TYPE": "application/json",
            "AUTHORIZATION": f"Bearer {access_token}",
        }
        return graphql_query(*args, **kwargs, headers=headers, client=client)

    return _client_query


@pytest.fixture
def expired_client_query(client, expired_access_token):
    def _client_query(*args, **kwargs):
        headers = {
            "CONTENT_TYPE": "application/json",
            "AUTHORIZATION": f"Bearer {expired_access_token}",
        }
        return graphql_query(*args, **kwargs, headers=headers, client=client)

    return _client_query


@pytest.fixture
def client_query_no_token(client):
    def _client_query(*args, **kwargs):
        headers = {
            "CONTENT_TYPE": "application/json",
        }
        return graphql_query(*args, **kwargs, headers=headers, client=client)

    return _client_query


@pytest.fixture
def landscapes():
    return mixer.cycle(2).blend(
        Landscape,
        area_polygon={
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [-104.9, 39.7]},
                }
            ],
        },
    )


@pytest.fixture
def managed_landscapes(users):
    landscapes = mixer.cycle(2).blend(Landscape)

    for i in range(len(landscapes)):
        landscapes[i].membership_list.save_membership(
            users[i].email,
            landscape_collaboration_roles.ROLE_MANAGER,
            CollaborationMembership.APPROVED,
        )

    return landscapes


@pytest.fixture
def landscape_user_memberships(managed_landscapes, users):
    memberships = [
        landscape.membership_list.save_membership(
            users[i + 1].email,
            landscape_collaboration_roles.ROLE_MEMBER,
            CollaborationMembership.APPROVED,
        )[1]
        for i, landscape in enumerate(managed_landscapes)
    ]
    return memberships


@pytest.fixture
def groups():
    return mixer.cycle(5).blend(
        Group,
        membership_list=mixer.blend(
            MembershipList, membership_type=MembershipList.MEMBERSHIP_TYPE_OPEN
        ),
    )


@pytest.fixture
def groups_closed():
    return mixer.cycle(2).blend(
        Group,
        membership_list=mixer.blend(
            MembershipList, membership_type=MembershipList.MEMBERSHIP_TYPE_CLOSED
        ),
    )


@pytest.fixture
def groups_closed_managers(groups_closed, users):
    return [
        group.membership_list.save_membership(
            users[i].email,
            group_collaboration_roles.ROLE_MANAGER,
            CollaborationMembership.APPROVED,
        )[1]
        for i, group in enumerate(groups_closed)
    ]


@pytest.fixture
def managed_groups(users, groups):
    for i in range(len(groups)):
        groups[i].add_manager(users[i])

    return groups


@pytest.fixture
def subgroups():
    return mixer.cycle(2).blend(Group)


@pytest.fixture
def users():
    return mixer.cycle(5).blend(User)


@pytest.fixture
def unsubscribe_token(users_with_group_notifications):
    return JWTService().create_unsubscribe_token(users_with_group_notifications[0])


@pytest.fixture
def users_with_group_notifications():
    users = mixer.cycle(5).blend(User)

    for user in users:
        mixer.blend(UserPreference, user=user, key=USER_PREFS_KEY_GROUP_NOTIFICATIONS, value="true")

    return users


@pytest.fixture
def users_with_story_map_notifications():
    users = mixer.cycle(5).blend(User)

    for user in users:
        mixer.blend(
            UserPreference, user=user, key=USER_PREFS_KEY_STORY_MAP_NOTIFICATIONS, value="true"
        )

    return users


@pytest.fixture
def group_associations(groups, subgroups):
    group_associations = []

    for group in groups:
        new_associations = mixer.cycle(2).blend(
            GroupAssociation, parent_group=group, child_group=(sg for sg in subgroups)
        )
        group_associations.extend(new_associations)

    return group_associations


@pytest.fixture
def group_manager_memberships(groups, users):
    return mixer.cycle(5).blend(
        CollaborationMembership,
        membership_list=(g.membership_list for g in groups),
        user=(u for u in users),
        user_role=group_collaboration_roles.ROLE_MANAGER,
    )


@pytest.fixture
def memberships_pending_with_notifications(groups, users_with_group_notifications):
    return mixer.cycle(5).blend(
        CollaborationMembership,
        membership_list=(g.membership_list for g in groups),
        user=(u for u in users_with_group_notifications),
        user_role=group_collaboration_roles.ROLE_MEMBER,
        membership_status=CollaborationMembership.PENDING,
    )


@pytest.fixture
def landscape_common_group(landscapes, groups):
    group = groups[1]
    landscape = landscapes[0]

    common_group = mixer.blend(
        LandscapeGroup, landscape=landscape, group=group, is_default_landscape_group=False
    )

    return common_group


@pytest.fixture
def make_core_db_records(
    group_associations, landscapes, landscape_common_group, groups, subgroups, users
):
    return


@pytest.fixture
def data_entry_current_user_file(users):
    creator = users[0]
    creator_group = mixer.blend(Group)
    creator_group.membership_list.save_membership(
        creator.email, group_collaboration_roles.ROLE_MEMBER, CollaborationMembership.APPROVED
    )
    resource = mixer.blend(
        SharedResource,
        target=creator_group,
        source=mixer.blend(
            DataEntry, slug=None, created_by=creator, size=100, entry_type=DataEntry.ENTRY_TYPE_FILE
        ),
    )
    return resource.source


@pytest.fixture
def data_entry_current_user_link(users):
    creator = users[0]
    creator_group = mixer.blend(Group)
    creator_group.membership_list.save_membership(
        creator.email, group_collaboration_roles.ROLE_MEMBER, CollaborationMembership.APPROVED
    )
    resource = mixer.blend(
        SharedResource,
        target=creator_group,
        source=mixer.blend(
            DataEntry, slug=None, created_by=creator, entry_type=DataEntry.ENTRY_TYPE_LINK
        ),
    )
    return resource.source


@pytest.fixture
def data_entry_other_user(users):
    creator = users[1]
    creator_group = mixer.blend(Group)
    creator_group.membership_list.save_membership(
        creator.email, group_collaboration_roles.ROLE_MEMBER, CollaborationMembership.APPROVED
    )
    resource = mixer.blend(
        SharedResource,
        target=creator_group,
        source=mixer.blend(DataEntry, slug=None, created_by=creator, size=100),
    )
    return resource.source


@pytest.fixture
def group_data_entries(users, groups):
    creator = users[0]
    creator_group = groups[0]
    resources = mixer.cycle(5).blend(
        SharedResource,
        target=creator_group,
        share_uuid=lambda: uuid.uuid4(),
        source=lambda: mixer.blend(DataEntry, created_by=creator, size=100, resource_type="csv"),
    )
    return [resource.source for resource in resources]


@pytest.fixture
def landscape_data_entries(users, landscapes):
    creator = users[0]
    creator_landscape = landscapes[0]
    resources = mixer.cycle(5).blend(
        SharedResource,
        target=creator_landscape,
        source=lambda: mixer.blend(
            DataEntry, created_by=creator, size=100, resource_type=(type for type in ("xls", "csv"))
        ),
    )
    return [resource.source for resource in resources]


@pytest.fixture
def data_entries(group_data_entries, landscape_data_entries):
    return group_data_entries + landscape_data_entries


@pytest.fixture
def data_entries_memberships(users, data_entries):
    user = users[0]
    for data_entry in data_entries:
        shared_resource = data_entry.shared_resources.first()
        shared_resource.target.membership_list.save_membership(
            user_email=user.email,
            user_role=landscape_collaboration_roles.ROLE_MEMBER,
            membership_status=CollaborationMembership.APPROVED,
        )


@pytest.fixture
def data_entry_kml(users, groups):
    creator = users[0]
    creator_group = groups[0]
    creator_group.membership_list.save_membership(
        creator.email, group_collaboration_roles.ROLE_MEMBER, CollaborationMembership.APPROVED
    )
    return mixer.blend(
        DataEntry,
        created_by=creator,
        size=100,
        groups=creator_group,
        entry_type=DataEntry.ENTRY_TYPE_FILE,
        resource_type="kml",
    )


@pytest.fixture
def data_entry_gpx(users, groups):
    creator = users[0]
    creator_group = groups[0]
    creator_group.members.add(creator)
    return mixer.blend(
        DataEntry,
        created_by=creator,
        size=100,
        groups=creator_group,
        entry_type=DataEntry.ENTRY_TYPE_FILE,
        resource_type="gpx",
    )


@pytest.fixture
def data_entry_shapefile(users, groups):
    creator = users[0]
    creator_group = groups[0]
    creator_group.membership_list.save_membership(
        creator.email, group_collaboration_roles.ROLE_MEMBER, CollaborationMembership.APPROVED
    )
    return mixer.blend(
        DataEntry,
        created_by=creator,
        size=100,
        groups=creator_group,
        entry_type=DataEntry.ENTRY_TYPE_FILE,
        resource_type="zip",
    )


@pytest.fixture
def visualization_config_current_user(users, data_entry_current_user_file, groups):
    creator = users[0]
    creator_group = groups[0]
    creator_group.membership_list.save_membership(
        creator.email, group_collaboration_roles.ROLE_MEMBER, CollaborationMembership.APPROVED
    )
    return mixer.blend(
        VisualizationConfig, created_by=creator, data_entry=data_entry_current_user_file
    )


@pytest.fixture
def visualization_config_other_user(users, data_entry_other_user, groups):
    creator = users[1]
    creator_group = groups[1]
    creator_group.membership_list.save_membership(
        creator.email, group_collaboration_roles.ROLE_MEMBER, CollaborationMembership.APPROVED
    )
    return mixer.blend(VisualizationConfig, created_by=creator, data_entry=data_entry_other_user)


@pytest.fixture
def visualization_configs(users, groups):
    creator = users[0]
    creator_group = groups[1]
    creator_group.membership_list.save_membership(
        creator.email, group_collaboration_roles.ROLE_MEMBER, CollaborationMembership.APPROVED
    )
    visualizations = mixer.cycle(5).blend(
        VisualizationConfig,
        created_by=creator,
        data_entry=lambda: mixer.blend(
            SharedResource,
            target=creator_group,
            source=lambda: mixer.blend(DataEntry, created_by=creator, size=100),
        ).source,
        owner=creator_group,
    )
    return visualizations


@pytest.fixture
def visualization_config_processing(users, groups):
    creator = users[0]
    creator_group = groups[1]
    creator_group.membership_list.save_membership(
        creator.email, group_collaboration_roles.ROLE_MEMBER, CollaborationMembership.APPROVED
    )
    visualizations = mixer.cycle(5).blend(
        VisualizationConfig,
        created_by=creator,
        data_entry=lambda: mixer.blend(
            SharedResource,
            target=creator_group,
            source=lambda: mixer.blend(DataEntry, created_by=creator, size=100),
        ).source,
        owner=creator_group,
        mapbox_tileset_id=lambda: uuid.uuid4(),
        mapbox_tileset_status=VisualizationConfig.MAPBOX_TILESET_PENDING,
    )
    return visualizations


@pytest.fixture
def taxonomy_terms():
    return mixer.cycle(10).blend(TaxonomyTerm)


@pytest.fixture
def story_maps(users):
    user_0_stories_published = mixer.cycle(2).blend(
        StoryMap, created_by=users[0], is_published=True
    )
    user_0_stories_drafts = mixer.cycle(3).blend(StoryMap, created_by=users[0], is_published=False)
    user_1_stories_published = mixer.cycle(4).blend(
        StoryMap, created_by=users[1], is_published=True
    )
    user_1_stories_drafts = mixer.cycle(5).blend(StoryMap, created_by=users[1], is_published=False)
    return (
        user_0_stories_published
        + user_0_stories_drafts
        + user_1_stories_published
        + user_1_stories_drafts
    )


@pytest.fixture
def story_map_membership_list(story_maps):
    story_map = story_maps[0]
    story_map.membership_list = mixer.blend(MembershipList)
    story_map.save()

    return story_map.membership_list


@pytest.fixture
def story_map_user_memberships(story_map_membership_list, users):
    return mixer.cycle(2).blend(
        CollaborationMembership,
        membership_list=story_map_membership_list,
        user=(u for u in users),
        pending_email=None,
    )


@pytest.fixture
def story_map_user_memberships_not_registered(story_map_membership_list):
    return mixer.cycle(2).blend(
        CollaborationMembership,
        membership_list=story_map_membership_list,
        user=None,
        pending_email=(mixer.faker.email() for _ in range(2)),
    )


@pytest.fixture
def story_map_user_memberships_approve_tokens(story_map_user_memberships):
    return [
        JWTService().create_token(
            membership.user,
            extra_payload={
                "membershipId": str(membership.id),
                "pendingEmail": None,
                "approveStoryMapMembership": True,
            },
        )
        for membership in story_map_user_memberships
    ]


@pytest.fixture
def story_map_user_memberships_not_registered_approve_tokens(
    story_map_user_memberships_not_registered,
):
    return [
        JWTService().create_token(
            None,
            extra_payload={
                "membershipId": str(membership.id),
                "pendingEmail": membership.pending_email,
                "approveStoryMapMembership": True,
            },
        )
        for membership in story_map_user_memberships_not_registered
    ]


@pytest.fixture
def audit_log_user():
    return mixer.blend(User)


@pytest.fixture
def site_with_depth_intervals(project):
    site = mixer.blend(Site, project=project)
    soil_data = mixer.blend(SoilData, site=site)
    for start in range(0, 20, 5):
        end = start + 5
        mixer.blend(
            SoilDataDepthInterval,
            soil_data=soil_data,
            depth_interval_start=start,
            depth_interval_end=end,
        )
    return site
