import pytest
from django.conf import settings
from mixer.backend.django import mixer

from apps.core.models import Group, User
from apps.shared_data.models import DataEntry


@pytest.fixture
def user():
    return mixer.blend(User)


@pytest.fixture
def user_b():
    return mixer.blend(User)


@pytest.fixture
def group():
    return mixer.blend(Group)


@pytest.fixture
def data_entry_filename():
    return "test_data.csv"


@pytest.fixture
def data_entry(user, data_entry_filename):
    return mixer.blend(
        DataEntry,
        size=1,
        url=f"{settings.DATA_ENTRY_FILE_BASE_URL}/{user.id}/{data_entry_filename}",
        created_by=user,
    )


@pytest.fixture
def data_entry_user_b(user_b, data_entry_filename):
    return mixer.blend(
        DataEntry,
        size=1,
        url=f"{settings.DATA_ENTRY_FILE_BASE_URL}/{user_b.id}/{data_entry_filename}",
        created_by=user_b,
    )
