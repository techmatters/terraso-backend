from datetime import datetime, timedelta

import pytest
from django.core.management import call_command
from mixer.backend.django import mixer

from apps.core.management.commands.harddelete import Command
from apps.core.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def deletion_gap():
    return Command.DEFAULT_DELETION_GAP


@pytest.fixture
def exec_date():
    return datetime.now()


@pytest.fixture
def delete_date(exec_date, deletion_gap):
    return exec_date - (deletion_gap + timedelta(days=1))


@pytest.fixture
def no_delete_date(exec_date, deletion_gap):
    return exec_date - (deletion_gap - timedelta(days=1))


def test_delete_user_deleted(exec_date, delete_date):
    user = mixer.blend(User)
    user.delete()
    user.deleted_at = delete_date
    user.save(keep_deleted=True)
    print(user.deleted_at)
    call_command("harddelete", exec_date=exec_date)
    assert (
        not User.objects.all(force_visibility=True).filter(id=user.id).exists()
    ), "User should be deleted"
