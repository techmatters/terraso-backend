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
    User,
)

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
def landscapes():
    return mixer.cycle(2).blend(Landscape)


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
