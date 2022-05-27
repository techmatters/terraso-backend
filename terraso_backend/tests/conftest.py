import pytest
from django.test.client import Client
from mixer.backend.django import mixer

from apps.auth.services import JWTService
from apps.core.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def users():
    return mixer.cycle(5).blend(User)


@pytest.fixture
def access_token(users):
    return JWTService().create_access_token(users[0])


@pytest.fixture
def logged_client(access_token):
    return Client(HTTP_AUTHORIZATION=f"Bearer {access_token}")
