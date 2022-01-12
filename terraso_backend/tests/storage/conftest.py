import pytest
from mixer.backend.django import mixer

from apps.auth.services import JWTService
from apps.core.models import User


@pytest.fixture
def access_token(user):
    return JWTService().create_access_token(user)


@pytest.fixture
def user():
    return mixer.blend(User)
