# Copyright © 2023 Technology Matters
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see https://www.gnu.org/licenses/.

import pytest
from django.core.management import call_command
from mixer.backend.django import mixer

from apps.core.models import Group, User
from apps.shared_data.models import DataEntry

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("model", [Group, DataEntry])
def test_delete_model_deleted(model, delete_date):
    obj = mixer.blend(model)
    obj.delete()
    obj.deleted_at = delete_date
    obj.save(keep_deleted=True)
    call_command("harddelete")
    assert (
        not model.objects.all(force_visibility=True).filter(id=obj.id).exists()
    ), "Model should be deleted"


@pytest.mark.parametrize("model", [User])
def test_delete_user_not_deleted(model, delete_date):
    obj = mixer.blend(model)
    obj.delete()
    obj.deleted_at = delete_date
    obj.save(keep_deleted=True)
    call_command("harddelete")
    assert (
        model.objects.all(force_visibility=True).filter(id=obj.id).exists()
    ), "Model should not be deleted"


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
