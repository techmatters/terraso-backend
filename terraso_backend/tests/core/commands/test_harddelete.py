import pytest
from django.core.management import call_command
from mixer.backend.django import mixer

from apps.core.models import Group, User
from apps.shared_data.models import DataEntry

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("model", [User, Group, DataEntry])
def test_delete_model_deleted(model, delete_date):
    obj = mixer.blend(model)
    obj.delete()
    obj.deleted_at = delete_date
    obj.save(keep_deleted=True)
    call_command("harddelete")
    assert (
        not model.objects.all(force_visibility=True).filter(id=obj.id).exists()
    ), "Model should be deleted"


@pytest.mark.parametrize("model", [User, Group, DataEntry])
def test_delete_model_not_deleted(model, no_delete_date):
    obj = mixer.blend(model)
    obj.delete()
    obj.deleted_at = no_delete_date
    obj.save(keep_deleted=True)
    call_command("harddelete")
    assert (
        model.objects.all(force_visibility=True).filter(id=obj.id).exists()
    ), "Model should not be deleted"
