import pytest
from graphene_django.utils.testing import graphql_query
from mixer.backend.django import mixer

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
def client_query(client):
    def _client_query(*args, **kwargs):
        return graphql_query(*args, **kwargs, client=client)

    return _client_query


@pytest.fixture
def landscapes():
    return mixer.cycle(2).blend(Landscape)


@pytest.fixture
def groups():
    return mixer.cycle(4).blend(Group)


@pytest.fixture
def subgroups():
    return mixer.cycle(2).blend(Group)


@pytest.fixture
def users():
    return mixer.cycle(2).blend(User)


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
        Membership, group=mixer.SELECT, user=mixer.SELECT, user_role=Membership.ROLE_MEMBER
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
