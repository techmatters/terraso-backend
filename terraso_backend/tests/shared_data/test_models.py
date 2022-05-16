import pytest
from mixer.backend.django import mixer

from apps.shared_data.models import DataEntry

pytestmark = pytest.mark.django_db
data_entry_size = 100

def test_data_entry_string_format_is_its_name():
    data_entry_name = "Test Survey Questions"
    data_entry = mixer.blend(DataEntry, name=data_entry_name, size=data_entry_size)

    assert data_entry_name == str(data_entry)


def test_data_entry_is_slugifiable_by_name():
    data_entry = mixer.blend(DataEntry, name="Test Survey Data", slug=None, size=data_entry_size)

    assert data_entry.slug == "test-survey-data"


def test_data_entry_can_be_updated_by_its_creator(user):
    users_data_entry = mixer.blend(DataEntry, created_by=user, size=data_entry_size)

    assert user.has_perm(DataEntry.get_perm("change"), obj=users_data_entry)


def test_data_entry_cannot_be_updated_by_non_creator(user, user_b):
    any_data_entry = mixer.blend(DataEntry, created_by=user_b, size=data_entry_size)

    assert not user.has_perm(DataEntry.get_perm("change"), obj=any_data_entry)


def test_data_entry_can_be_deleted_by_its_creator(user):
    users_data_entry = mixer.blend(DataEntry, created_by=user, size=data_entry_size)

    assert user.has_perm(DataEntry.get_perm("delete"), obj=users_data_entry)


def test_data_entry_cannot_be_deleted_by_non_creator(user, user_b):
    any_data_entry = mixer.blend(DataEntry, created_by=user_b, size=data_entry_size)

    assert not user.has_perm(DataEntry.get_perm("delete"), obj=any_data_entry)


def test_data_entry_can_be_viewed_by_group_members(user, user_b, group):
    group.members.add(user, user_b)

    group_data_entry = mixer.blend(DataEntry, created_by=user, size=data_entry_size)
    group_data_entry.groups.add(group)

    assert user_b.has_perm(DataEntry.get_perm("view"), obj=group_data_entry)


def test_data_entry_cannot_be_viewed_by_non_group_members(user, user_b, group):
    group.members.add(user)

    group_data_entry = mixer.blend(DataEntry, created_by=user, size=data_entry_size)
    group_data_entry.groups.add(group)

    assert not user_b.has_perm(DataEntry.get_perm("view"), obj=group_data_entry)
