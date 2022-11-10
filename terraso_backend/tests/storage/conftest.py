import pytest
from mixer.backend.django import mixer

from apps.auth.services import JWTService
from apps.core.models import Group, Landscape, LandscapeGroup, User


@pytest.fixture
def access_token(user):
    return JWTService().create_access_token(user)


@pytest.fixture
def user():
    return mixer.blend(User)


@pytest.fixture
def landscape(user):
    landscape = mixer.blend(Landscape)
    group = mixer.blend(Group)
    group.add_manager(user)
    mixer.blend(LandscapeGroup, landscape=landscape, group=group, is_default_landscape_group=True)
    return landscape
