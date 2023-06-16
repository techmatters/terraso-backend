import pytest
from django.core.management import call_command
from mixer.backend.django import mixer

from apps.core.models import Group, User
from apps.shared_data.models import DataEntry

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("model", [User, Group, DataEntry])
def test_delete_model_deleted(model, exec_time, delete_date):
    obj = mixer.blend(model)
    obj.delete()
    obj.deleted_at = delete_date
    obj.save(keep_deleted=True)
    call_command("harddelete", exec_time=exec_time)
    assert (
        not model.objects.all(force_visibility=True).filter(id=obj.id).exists()
    ), "User should be deleted"


@pytest.mark.parametrize("model", [User, Group, DataEntry])
def test_delete_model_not_deleted(model, exec_time, no_delete_date):
    obj = mixer.blend(model)
    obj.delete()
    obj.deleted_at = no_delete_date
    obj.save(keep_deleted=True)
    call_command("harddelete", exec_time=exec_time)
    assert (
        model.objects.all(force_visibility=True).filter(id=obj.id).exists()
    ), "User should not be deleted"
