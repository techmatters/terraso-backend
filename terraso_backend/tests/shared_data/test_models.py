import pytest
from mixer.backend.django import mixer

from apps.shared_data.models import DataEntry

pytestmark = pytest.mark.django_db


def test_data_entry_string_format_is_its_name():
    data_entry_name = "Test Survey Questions"
    data_entry = mixer.blend(DataEntry, name=data_entry_name)

    assert data_entry_name == str(data_entry)


def test_data_entry_is_slugifiable_by_name():
    data_entry = mixer.blend(DataEntry, name="Test Survey Data", slug=None)

    assert data_entry.slug == "test-survey-data"
