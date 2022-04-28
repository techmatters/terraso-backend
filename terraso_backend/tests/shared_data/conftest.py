import pytest
from mixer.backend.django import mixer

from apps.core.models import Group, User


@pytest.fixture
def user():
    return mixer.blend(User)


@pytest.fixture
def user_b():
    return mixer.blend(User)


@pytest.fixture
def group():
    return mixer.blend(Group)
