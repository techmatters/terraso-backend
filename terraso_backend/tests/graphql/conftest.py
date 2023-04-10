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

from datetime import timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time
from graphene_django.utils.testing import graphql_query
from mixer.backend.django import mixer

from apps.auth.services import JWTService
from apps.core.models import (
    Group,
    GroupAssociation,
    Landscape,
    LandscapeGroup,
    Membership,
    TaxonomyTerm,
    User,
    UserPreference,
)
from apps.shared_data.models import DataEntry, VisualizationConfig
from apps.story_map.models import StoryMap

pytestmark = pytest.mark.django_db


@pytest.fixture
def access_token(users):
    return JWTService().create_access_token(users[0])


@pytest.fixture
@freeze_time(timezone.now() - timedelta(days=10))
def expired_access_token(users):
    return JWTService().create_access_token(users[0])


@pytest.fixture
def client_query(client, access_token):
    def _client_query(*args, **kwargs):
        headers = {
            "CONTENT_TYPE": "application/json",
            "HTTP_AUTHORIZATION": f"Bearer {access_token}",
        }
        return graphql_query(*args, **kwargs, headers=headers, client=client)

    return _client_query


@pytest.fixture
def expired_client_query(client, expired_access_token):
    def _client_query(*args, **kwargs):
        headers = {
            "CONTENT_TYPE": "application/json",
            "HTTP_AUTHORIZATION": f"Bearer {expired_access_token}",
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
        group = mixer.blend(Group)
        group.add_manager(users[i])
        mixer.blend(
            LandscapeGroup,
            landscape=landscapes[i],
            group=group,
            is_default_landscape_group=True,
        )

    return landscapes


@pytest.fixture
def groups():
    return mixer.cycle(5).blend(Group)


@pytest.fixture
def groups_closed():
    return mixer.cycle(2).blend(Group, membership_type=Group.MEMBERSHIP_TYPE_CLOSED)


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
def users_with_notifications():
    users = mixer.cycle(5).blend(User)

    for user in users:
        mixer.blend(UserPreference, user=user, key="notifications", value="true")

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
def memberships(groups, users):
    return mixer.cycle(5).blend(
        Membership,
        group=(g for g in groups),
        user=(u for u in users),
        user_role=Membership.ROLE_MANAGER,
    )


@pytest.fixture
def memberships_pending(groups, users):
    return mixer.cycle(5).blend(
        Membership,
        group=(g for g in groups),
        user=(u for u in users),
        user_role=Membership.ROLE_MEMBER,
        membership_status=Membership.PENDING,
    )


@pytest.fixture
def memberships_pending_with_notifications(groups, users_with_notifications):
    return mixer.cycle(5).blend(
        Membership,
        group=(g for g in groups),
        user=(u for u in users_with_notifications),
        user_role=Membership.ROLE_MEMBER,
        membership_status=Membership.PENDING,
    )


@pytest.fixture
def landscape_groups(landscapes, groups):
    first_group, second_group = groups[0], groups[1]
    landscape = landscapes[0]

    default_group = mixer.blend(
        LandscapeGroup, landscape=landscape, group=first_group, is_default_landscape_group=True
    )
    common_group = mixer.blend(LandscapeGroup, landscape=landscape, group=second_group)

    return [default_group, common_group]


@pytest.fixture
def make_core_db_records(
    group_associations, landscapes, landscape_groups, memberships, groups, subgroups, users
):
    return


@pytest.fixture
def data_entry_current_user_file(users, groups):
    creator = users[0]
    creator_group = groups[0]
    creator_group.members.add(creator)
    return mixer.blend(
        DataEntry,
        slug=None,
        created_by=creator,
        size=100,
        groups=creator_group,
        entry_type=DataEntry.ENTRY_TYPE_FILE,
    )


@pytest.fixture
def data_entry_current_user_link(users, groups):
    creator = users[0]
    creator_group = groups[0]
    creator_group.members.add(creator)
    return mixer.blend(
        DataEntry,
        slug=None,
        created_by=creator,
        groups=creator_group,
        entry_type=DataEntry.ENTRY_TYPE_LINK,
    )


@pytest.fixture
def data_entry_other_user(users, groups):
    creator = users[1]
    creator_group = groups[1]
    creator_group.members.add(creator)
    return mixer.blend(DataEntry, slug=None, created_by=creator, size=100, groups=creator_group)


@pytest.fixture
def data_entries(users, groups):
    creator = users[0]
    creator_group = groups[0]
    creator_group.members.add(creator)
    return mixer.cycle(5).blend(DataEntry, created_by=creator, size=100, groups=creator_group)


@pytest.fixture
def visualization_config_current_user(users, data_entry_current_user_file, groups):
    creator = users[0]
    creator_group = groups[0]
    creator_group.members.add(creator)
    return mixer.blend(
        VisualizationConfig, created_by=creator, data_entry=data_entry_current_user_file
    )


@pytest.fixture
def visualization_config_other_user(users, data_entry_other_user, groups):
    creator = users[1]
    creator_group = groups[1]
    creator_group.members.add(creator)
    return mixer.blend(VisualizationConfig, created_by=creator, data_entry=data_entry_other_user)


@pytest.fixture
def visualization_configs(users, groups):
    creator = users[0]
    creator_group = groups[1]
    creator_group.members.add(creator)
    visualizations = mixer.cycle(5).blend(
        VisualizationConfig,
        created_by=creator,
        data_entry=lambda: mixer.blend(
            DataEntry, created_by=creator, size=100, groups=creator_group
        ),
        group=groups[0],
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
