import pytest
from django.contrib.auth.models import User
from mixer.backend.django import mixer

pytestmark = pytest.mark.django_db


def test_user_creation():
    user = mixer.blend(User)
    assert user.id
